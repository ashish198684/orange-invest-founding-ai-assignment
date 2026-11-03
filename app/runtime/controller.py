from contextlib import nullcontext
from contextvars import ContextVar
from app.workflow import WorkflowController,SafetyError
from app.runtime.pg import PgStore
from app.runtime.provider_client import ProviderClient
from app.runtime.model import IsolatedModel
from app.runtime.memory import Memory
from app.runtime.observe import active
from app.agent.groq import GroqInterpreter
_memory_revision=ContextVar('memory_revision',default=None)

class PgController(WorkflowController):
    def __init__(self,user_id,*,fence=None,provider=None,database=None):
        super().__init__('postgres-runtime',user_id=user_id,provider=provider or ProviderClient(user_id),
                         store=PgStore(user_id,fence=fence,database=database),execution_scope=nullcontext)
        self.interpreter=IsolatedModel()

    def _validate_correction_context(self,db,w):
        guard=getattr(self,'_proposal_guard',None)
        if guard and (w['revision']!=guard[0] or Memory(self.context.user_id).revision(db)!=guard[1]):
            raise SafetyError('model_context_changed_retry')

    def chat_live(self,workflow_id,text):
        if not isinstance(text,str) or not 1<=len(text)<=4000:raise SafetyError('invalid_message')
        if text.strip().lower() in {'yes','y','confirm','approved','approve','ok','okay'}:raise SafetyError('approval_required')
        memory=Memory(self.context.user_id)
        with self.store.connect() as db:
            w=self._owned(db,workflow_id);revision=w['revision'];memory_revision=memory.revision(db)
            context=self._draft(w,db)
            if memory_revision!=memory.revision(db):raise SafetyError('model_context_changed_retry')
        model=GroqInterpreter()
        # No transaction is held during the remote model. Reviews, approval IDs,
        # operation keys, user identity and raw history never enter its context.
        patch=model.interpret(text,self._now(),context)
        self._proposal_guard=(revision,memory_revision)
        try:
            if patch:self.propose(workflow_id,patch)
            else:
                with self.store.connect() as db:self._validate_correction_context(db,self._owned(db,workflow_id))
        finally:self._proposal_guard=None
        question=self.next_question(workflow_id);view=self.view(workflow_id)
        action=model.last_result['action_proposal']
        if action=='show_bookings':question=None
        message=('Your appointments below are read from the provider records.' if action=='show_bookings' else question['message'] if question else
                 'Choose the appointment below, then review a fresh '+action+' approval card.' if action in {'cancel','reschedule'} else
                 'Your plan is ready below. Review an available slot and its exact quote before approving.')
        return {'workflow':view,'question':question,'message':message,'action_proposal':action,
                'model':{'mode':'groq',**model.last_result}}

    def search(self,workflow_id):
        memory=Memory(self.context.user_id);before=memory.revision()
        result=super().search(workflow_id)
        if before!=memory.revision():raise SafetyError('memory_changed_retry')
        return result

    def prepare_booking(self,*args,**kwargs):
        token=_memory_revision.set(Memory(self.context.user_id).revision())
        try:return super().prepare_booking(*args,**kwargs)
        finally:_memory_revision.reset(token)

    def _approval(self,db,w,snapshot):
        before=_memory_revision.get()
        if before is not None and before!=Memory(self.context.user_id).revision(db):
            raise SafetyError('memory_changed_retry')
        return super()._approval(db,w,snapshot)

    def _draft(self,w,db=None):
        raw=super()._draft(w,db)
        memory=Memory(self.context.user_id).context(db)
        if 'area' not in raw and 'area' in memory:raw['area']=memory['area']
        preferences={k:memory[k] for k in ['earliest_hour','technician'] if k in memory}
        if preferences:raw['preferences']={**preferences,**raw.get('preferences',{})}
        return raw

    def _state(self,db,wid,state):
        before=self._owned(db,wid)['status']
        super()._state(db,wid,state)
        run=active.get()
        if run:run.emit('workflow_transition',state_before=before,state_after=state)

    def _valid_snapshot(self,db,w,a):
        s=super()._valid_snapshot(db,w,a)
        job=db.execute('SELECT * FROM jobs WHERE operation_id IN '
                       '(SELECT operation_id FROM operations WHERE approval_id=?)',(a['approval_id'],)).fetchone()
        if job:
            op=db.execute('SELECT attempts FROM operations WHERE operation_id=?',(job['operation_id'],)).fetchone()
            expired=db.execute('SELECT clock_timestamp()>initiation_deadline FROM jobs WHERE operation_id=?',(job['operation_id'],)).fetchone()[0]
            if op['attempts']==0 and expired:raise SafetyError('initiating_run_expired')
        return s

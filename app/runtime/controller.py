from contextlib import nullcontext
from contextvars import ContextVar
import re
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

    @staticmethod
    def _prior_service_reference(text):
        """Only a user's explicit 'same ... as last time' phrase triggers history lookup."""
        m=re.search(r'\bsame\s+(electrician|plumber|ac servicing)\s+as\s+(?:the\s+)?last\s+time\b',text,re.I)
        return m.group(1).lower() if m else None

    def _ground_prior_provider(self,text,patch):
        """Lookup the authenticated user's provider history, never model memory.

        The fixed list_bookings contract has no created_at; when more than one
        historical provider matches, last-time ordering is unprovable.
        """
        service=self._prior_service_reference(text)
        if not service:return patch,None
        if patch.get('service') not in (None,service):
            raise SafetyError('history_service_conflict')
        patch={**patch,'service':service}
        history=self.provider.list_bookings(self.context.user_id)
        matches={b['provider'] for b in history if b.get('service')==service and b.get('status')=='booked'}
        if not matches:
            return patch,'I could not find a previous '+service+' booking in this account. Please choose a provider from the results.'
        if len(matches)>1:
            return patch,('I found multiple previous '+service+' providers. The booking list has no '
                          'creation timestamps, so I cannot identify the last one. Choose a provider from the results.')
        provider_id=next(iter(matches))
        detail=self.provider.get_provider(provider_id)
        attributes=detail.get('attributes',{})
        if detail.get('id')!=provider_id or attributes.get('service')!=service:
            raise SafetyError('history_provider_mismatch')
        area=attributes.get('area')
        if not area:raise SafetyError('history_provider_missing_area')
        if patch.get('area') not in (None,area):
            return patch,('Your previous '+service+' provider serves '+area+
                          ', which conflicts with the new requested area. Please clarify before selecting a slot.')
        patch={**patch,'provider_id':provider_id,'area':area}
        return patch,('I found your previous '+service+' provider in '+area+
                      '. You will still review and approve the exact new quote and slot.')

    @staticmethod
    def _explicit_change_action(text):
        """Recognize only an explicit customer request to *prepare* a change."""
        if re.search(r"\b(?:do not|don't|dont|never|not)\s+(?:\w+\s+){0,4}(?:move|reschedule|cancel)\b",text,re.I):
            return 'plan'
        if re.search(r'\b(?:move|reschedule)\s+(?:my|the)\s+.{0,40}\b(?:servicing|appointment|booking)\b',text,re.I):
            return 'reschedule'
        if re.search(r'\bcancel\s+(?:my|the)\s+.{0,40}\b(?:servicing|appointment|booking)\b',text,re.I):
            return 'cancel'
        return None

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
        patch,history_note=self._ground_prior_provider(text,patch)
        self._proposal_guard=(revision,memory_revision)
        try:
            if patch:self.propose(workflow_id,patch)
            else:
                with self.store.connect() as db:self._validate_correction_context(db,self._owned(db,workflow_id))
        finally:self._proposal_guard=None
        question=self.next_question(workflow_id);view=self.view(workflow_id)
        action=model.last_result['action_proposal']
        explicit_action=self._explicit_change_action(text)
        if explicit_action is not None:
            action=explicit_action
        if action in {'show_bookings','cancel','reschedule'}:question=None
        message=('Your appointments below are read from the provider records.' if action=='show_bookings' else question['message'] if question else
                 'Choose the appointment below, then review a fresh '+action+' approval card.' if action in {'cancel','reschedule'} else
                 'Your plan is ready below. Review an available slot and its exact quote before approving.')
        if history_note:message=history_note+' '+message
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

from contextlib import nullcontext
from app.workflow import WorkflowController,SafetyError
from app.runtime.pg import PgStore
from app.runtime.provider_client import ProviderClient
from app.runtime.model import IsolatedModel
from app.runtime.memory import Memory
from app.runtime.observe import active

class PgController(WorkflowController):
    def __init__(self,user_id,*,fence=None,provider=None):
        super().__init__('postgres-runtime',user_id=user_id,provider=provider or ProviderClient(user_id),
                         store=PgStore(user_id,fence=fence),execution_scope=nullcontext)
        self.interpreter=IsolatedModel()

    def _draft(self,w):
        raw=super()._draft(w)
        memory=Memory(self.context.user_id).context()
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

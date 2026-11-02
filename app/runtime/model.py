"""Proposal-only scripted model, isolated so a blocked interpreter is killable."""
import multiprocessing as mp
import time
from threading import BoundedSemaphore
from app.agent.scripted import ScriptedModel
from app.runtime.observe import active,BudgetExceeded,tracer
_slots=BoundedSemaphore(2)

def _interpret(pipe,text,now,delay):
    try:
        if delay:time.sleep(delay)
        pipe.send(ScriptedModel().interpret(text,now))
    finally:pipe.close()

class IsolatedModel:
    def __init__(self,delay=0):self.delay=delay
    def interpret(self,text,now):
        run=active.get()
        if run:run.charge('model')
        if not _slots.acquire(timeout=run.remaining() if run else 5):raise BudgetExceeded('model_capacity')
        try:return self._interpret(text,now)
        finally:_slots.release()
    def _interpret(self,text,now):
        run=active.get()
        limit=run.remaining() if run else 5
        context=mp.get_context('spawn');recv,send=context.Pipe(duplex=False)
        child=context.Process(target=_interpret,args=(send,text,now,self.delay))
        with tracer.start_as_current_span('model.proposal',record_exception=False):
            child.start();send.close()
            try:
                if not recv.poll(limit):raise BudgetExceeded('model_wall_limit')
                return recv.recv()
            finally:
                if child.is_alive():child.terminate()
                child.join(timeout=.2)
                if child.is_alive():child.kill();child.join(timeout=.2)
                recv.close()

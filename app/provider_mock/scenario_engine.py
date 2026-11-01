"""Constructor-only fixture control; never accepted from user/chat tool arguments."""

from dataclasses import asdict, dataclass
import hashlib


BOOK_BRANCHES = ('book_success', 'slot_taken', 'timeout_after_success',
                 'timeout_without_booking', 'hold_expired')


@dataclass(frozen=True)
class ScenarioConfig:
    seed: int = 20261101
    scenario_id: str = 'baseline'
    book_branch: str | None = None
    quote_delta: int = 0
    reschedule_conflicts: tuple[str, ...] = ()

    def __post_init__(self):
        if self.book_branch is not None and self.book_branch not in BOOK_BRANCHES:
            raise ValueError('Unknown forced book branch')
        if not isinstance(self.quote_delta, int) or self.quote_delta < 0:
            raise ValueError('quote_delta must be a nonnegative integer INR amount')

    def to_dict(self):
        return asdict(self)

    def branch_for(self, key):
        if self.book_branch:
            return self.book_branch
        # Independent stable draws across keys/seeds, unaffected by call ordering.
        data = f'{self.seed}\0{self.scenario_id}\0{key}'.encode()
        draw = int.from_bytes(hashlib.sha256(data).digest()[:8], 'big') / 2**64
        if draw < .70:
            return 'book_success'
        if draw < .85:
            return 'slot_taken'
        return 'timeout_after_success' if draw < .925 else 'timeout_without_booking'

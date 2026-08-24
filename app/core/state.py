from dataclasses import dataclass, field
from typing import Optional, Literal

@dataclass
class UserData:
    patient_uuid: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    is_new_customer: bool = True

    pending_tests: list[str] = field(default_factory=list)
    requires_prescription: Optional[bool] = None
    prescription_upload_link_sent: bool = False
    mode_of_sample_collection: Optional[Literal["Visit Center", "Home Visit"]] = None
    mode_of_payment: Optional[Literal["UPI", "Cash on Visit"]] = None
    chosen_slot: Optional[str] = None

    verification_attempts: int = 0

    def reset_verification(self) -> None:
        self.verification_attempts = 0

    def is_identity_verified(self) -> bool:
        return self.patient_uuid is not None
from dataclasses import dataclass


@dataclass(slots=True)
class PeerState:
    choking: bool = True
    interested: bool = False

    am_choking: bool = True
    am_interested: bool = False


    def reset(self) -> None:
        self.choking = True
        self.interested = False

        self.am_choking = True
        self.am_interested = False
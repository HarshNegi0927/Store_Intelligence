import uuid

class VisitorTracker:
    def __init__(self):
        self.registry = {}      # camera_track_id → visitor_id
        self.seq = {}           # visitor_id → sequence
        self.active = {}        # camera_track_id → frame count
        self.exited = set()     # visitor_ids who exited

    def get_visitor_id(self, track_id: int, camera_id: str) -> str:
        key = f"{camera_id}_{track_id}"
        if key not in self.registry:
            self.registry[key] = f"VIS_{uuid.uuid4().hex[:6]}"
            self.seq[self.registry[key]] = 0
            self.active[key] = 0
        return self.registry[key]

    def increment(self, track_id: int, camera_id: str):
        key = f"{camera_id}_{track_id}"
        self.active[key] = self.active.get(key, 0) + 1

    def next_seq(self, visitor_id: str) -> int:
        self.seq[visitor_id] = self.seq.get(visitor_id, 0) + 1
        return self.seq[visitor_id]

    def presence_ratio(self, track_id: int, camera_id: str, total: int) -> float:
        key = f"{camera_id}_{track_id}"
        return self.active.get(key, 0) / max(total, 1)

    def mark_exited(self, visitor_id: str):
        self.exited.add(visitor_id)

    def is_reentry(self, visitor_id: str) -> bool:
        return visitor_id in self.exited
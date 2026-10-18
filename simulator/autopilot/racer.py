"""Gate racer: follows a RacingLine with the FlightController and keeps score."""
import math
from dataclasses import dataclass, field

from .control import FlightController
from .geometry import dot, norm, sub, unit
from .planner import RacingLine


@dataclass
class Progress:
    gate_index: int = 0
    gate_times: list = field(default_factory=list)
    missed: list = field(default_factory=list)
    finished: bool = False
    start_t: float = None


class Racer:
    def __init__(self, line: RacingLine, controller: FlightController = None, lookahead=0.15,
                 gate_margin=0.15):
        self.line = line
        self.ctl = controller or FlightController()
        self.lookahead = lookahead          # s of travel the reference leads the drone
        self.gate_margin = gate_margin
        self.idx = 0
        self.prev_pos = None
        self.progress = Progress()
        self.max_cross_track = 0.0

    def step(self, state):
        line, prog = self.line, self.progress
        if prog.start_t is None:
            prog.start_t = state.t
        self.ctl.observe(state)
        self.idx = line.closest(state.pos, self.idx)
        speed_here = line.speed[self.idx]
        p_ref, v_ref, a_ref, tangent = line.reference(self.idx, self.lookahead * max(2.0, speed_here) * 0.3)
        cross_track = norm(sub(state.pos, line.points[self.idx]))
        self.max_cross_track = max(self.max_cross_track, cross_track)
        # look where we are going: ahead along the line
        _, _, _, ahead = line.reference(self.idx, max(3.0, 0.4 * speed_here))
        cmd = self.ctl.track(state, p_ref, v_ref, a_ref, ahead)
        self._score(state)
        return cmd

    def _score(self, state):
        prog = self.progress
        if self.prev_pos is not None and prog.gate_index < len(self.line.gate_sequence):
            gate = self.line.gate_sequence[prog.gate_index]
            a = dot(sub(self.prev_pos, gate.center), gate.normal)
            b = dot(sub(state.pos, gate.center), gate.normal)
            if a < 0 <= b and norm(sub(state.pos, gate.center)) < 3 * max(gate.width, gate.height):
                if gate.crossed(self.prev_pos, state.pos, 0.0):
                    prog.gate_times.append(state.t - prog.start_t)
                else:
                    prog.missed.append(prog.gate_index)
                prog.gate_index += 1
                if prog.gate_index == len(self.line.gate_sequence):
                    prog.finished = True
        self.prev_pos = state.pos

    @property
    def done(self):
        return self.progress.finished or self.idx >= len(self.line.points) - 2

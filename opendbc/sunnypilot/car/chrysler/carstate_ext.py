"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

from enum import StrEnum

from opendbc.car import Bus, structs
from opendbc.can.parser import CANParser
from opendbc.car.chrysler.values import RAM_HD
from opendbc.sunnypilot.car.chrysler.values_ext import BUTTONS


class CarStateExt:
  def __init__(self, CP, CP_SP):
    self.CP = CP
    self.CP_SP = CP_SP

    self.button_events = []
    self.button_states = {button.event_type: False for button in BUTTONS}

    # APA state tracking
    self.autopark_active = False           # True when factory APA has steering control
    self.autopark_status = 0              # raw AUTO_PARK_STATUS value from msg 671

  def update(self, ret: structs.CarState, ret_sp: structs.CarStateSP, can_parsers: dict[StrEnum, CANParser]):
    cp = can_parsers[Bus.pt]

    # ── Button events ──────────────────────────────────────────────────────
    button_events = []
    for button in BUTTONS:
      state = (cp.vl[button.can_addr][button.can_msg] in button.values)
      if self.button_states[button.event_type] != state:
        event = structs.CarState.ButtonEvent.new_message()
        event.type = button.event_type
        event.pressed = state
        button_events.append(event)
      self.button_states[button.event_type] = state
    self.button_events = button_events

    if self.CP.carFingerprint in RAM_HD:
      ret.steeringAngleDeg = cp.vl["STEERING"]["STEERING_ANGLE"]

    # ── Factory APA detection ────────────────────────────────────────────────────
    # EPS_2 msg 544: LKAS_STATE == 2 means autopark has taken steering control
    # LKAS_STATE == 8 = LKAS actuatable (normal op), 4 = fault
    lkas_state = cp.vl["EPS_2"]["LKAS_STATE"]
    self.autopark_active = (lkas_state == 2)

    # Secondary check via AUTO_PARK_REQUEST msg 671
    # AUTO_PARK_STATUS: 1=idle, 9=start, 10/11=active steering
    # Flag early before EPS switches if APA is already requesting
    try:
      self.autopark_status = cp.vl["AUTO_PARK_REQUEST"]["AUTO_PARK_STATUS"]
      if self.autopark_status >= 9:
        self.autopark_active = True
    except (KeyError, AttributeError):
      pass  # message not available on all model years

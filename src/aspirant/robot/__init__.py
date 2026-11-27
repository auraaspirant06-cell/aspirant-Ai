"""Animated 3D AI Robot state & animation controller package."""

from aspirant.robot.animation_controller import ROBOT_STATE_PROFILES, RobotAnimationProfile, compute_animation_frame
from aspirant.robot.avatar_controller import ROBOT_STATES, RobotAvatarController, RobotState

__all__ = [
    "ROBOT_STATES",
    "ROBOT_STATE_PROFILES",
    "RobotAnimationProfile",
    "RobotAvatarController",
    "RobotState",
    "compute_animation_frame",
]

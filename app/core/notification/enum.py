from enum import Enum


class NotificationDecisionResult(str, Enum):
    PROJECT_DISABLED = "project_disabled"
    SERVICE_DISABLED = "service_disabled"
    INCIDENT_CONDITION_NOT_MET = "incident_condition_not_met"
    USER_PLAN_NOT_ALLOWED = "user_plan_not_allowed"
    ALLOWED = "allowed"
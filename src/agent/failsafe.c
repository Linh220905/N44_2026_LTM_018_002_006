#include "failsafe.h"
#include <string.h>
#include <stdio.h>
#include <math.h>

void failsafe_init(failsafe_monitor_t *mon, const geofence_box_t *box) {
    if (!mon) return;

    memset(mon, 0, sizeof(failsafe_monitor_t));
    mon->timeout_us = DEFAULT_HEARTBEAT_TIMEOUT_US;
    mon->battery_remaining = 1.0f; // Mặc định 100% pin
    mon->is_triggered = false;
    mon->reason = FAILSAFE_NONE;
    mon->action_callback = NULL;
    mon->callback_user_data = NULL;

    if (box) {
        mon->fence = *box;
    } else {
        // Mặc định vô hiệu hoá nếu không truyền box
        memset(&mon->fence, 0, sizeof(geofence_box_t));
    }
}

void failsafe_update_heartbeat(failsafe_monitor_t *mon, uint64_t now_us) {
    if (!mon) return;
    mon->last_heartbeat_us = now_us;
}

void failsafe_update_battery(failsafe_monitor_t *mon, float battery_remaining) {
    if (!mon) return;
    mon->battery_remaining = battery_remaining;
}

void failsafe_set_action_callback(failsafe_monitor_t *mon,
                                  failsafe_action_callback_t cb,
                                  void *user_data) {
    if (!mon) return;
    mon->action_callback = cb;
    mon->callback_user_data = user_data;
}

static void dispatch_emergency_command(failsafe_monitor_t *mon, failsafe_reason_t reason, double x, double y, double z) {
    memset(&mon->last_emergency_cmd, 0, sizeof(failsafe_mavlink_cmd_t));

    switch (reason) {
        case FAILSAFE_HEARTBEAT_TIMEOUT:
            // Mất kết nối GCS: Chuyển sang AUTO_HOVER giữ nguyên tọa độ chờ tín hiệu kết nối lại
            mon->last_emergency_cmd.command = MAV_CMD_DO_SET_MODE;
            mon->last_emergency_cmd.param1 = (float)FLIGHT_MODE_AUTO_HOVER;
            mon->last_emergency_cmd.param5 = (float)x;
            mon->last_emergency_cmd.param6 = (float)y;
            mon->last_emergency_cmd.param7 = (float)z;
            snprintf(mon->last_emergency_cmd.description,
                     sizeof(mon->last_emergency_cmd.description),
                     "MAV_CMD_DO_SET_MODE: AUTO_HOVER (Loss of GCS Heartbeat)");
            break;

        case FAILSAFE_GEOFENCE_BREACH:
            // Bay ra ngoài Geofence: Kích hoạt hạ cánh khẩn cấp MAV_CMD_NAV_LAND ngay lập tức
            mon->last_emergency_cmd.command = MAV_CMD_NAV_LAND;
            mon->last_emergency_cmd.param5 = (float)x;
            mon->last_emergency_cmd.param6 = (float)y;
            mon->last_emergency_cmd.param7 = (float)z;
            snprintf(mon->last_emergency_cmd.description,
                     sizeof(mon->last_emergency_cmd.description),
                     "MAV_CMD_NAV_LAND: Geofence breach at (%.1f, %.1f, %.1f)", x, y, z);
            break;

        case FAILSAFE_BATTERY_LOW:
            // Pin dưới 10%: Hạ cánh khẩn cấp an toàn
            mon->last_emergency_cmd.command = MAV_CMD_NAV_LAND;
            mon->last_emergency_cmd.param5 = (float)x;
            mon->last_emergency_cmd.param6 = (float)y;
            mon->last_emergency_cmd.param7 = (float)z;
            snprintf(mon->last_emergency_cmd.description,
                     sizeof(mon->last_emergency_cmd.description),
                     "MAV_CMD_NAV_LAND: Critical low battery (%.1f%%)",
                     mon->battery_remaining <= 1.0f ? mon->battery_remaining * 100.0f : mon->battery_remaining);
            break;

        case FAILSAFE_EMERGENCY_TRIGGER:
            // Lệnh dừng khẩn cấp từ GCS: Ngay lập tức hạ cánh/ngắt nguồn an toàn
            mon->last_emergency_cmd.command = MAV_CMD_NAV_LAND;
            snprintf(mon->last_emergency_cmd.description,
                     sizeof(mon->last_emergency_cmd.description),
                     "MAV_CMD_NAV_LAND: Manual emergency kill triggered");
            break;

        default:
            return;
    }

    if (mon->action_callback) {
        mon->action_callback(mon, &mon->last_emergency_cmd, mon->callback_user_data);
    }
}

void failsafe_trigger_emergency(failsafe_monitor_t *mon) {
    if (!mon) return;
    mon->is_triggered = true;
    mon->reason = FAILSAFE_EMERGENCY_TRIGGER;
    dispatch_emergency_command(mon, FAILSAFE_EMERGENCY_TRIGGER, 0.0, 0.0, 0.0);
}

failsafe_reason_t failsafe_check(failsafe_monitor_t *mon, uint64_t now_us, double x, double y, double z) {
    if (!mon) return FAILSAFE_NONE;

    // Nếu đã kích hoạt Failsafe trước đó, giữ nguyên trạng thái
    if (mon->is_triggered) {
        return mon->reason;
    }

    failsafe_reason_t detected = FAILSAFE_NONE;

    // 1. Kiểm tra hàng rào địa lý 3D Geofence (Ưu tiên hàng đầu tránh va chạm vật lý)
    if (geofence_is_breached(&mon->fence, x, y, z)) {
        detected = FAILSAFE_GEOFENCE_BREACH;
    }
    // 2. Kiểm tra mất tín hiệu Heartbeat từ GCS (> timeout_us)
    else if (mon->last_heartbeat_us > 0 && (now_us > mon->last_heartbeat_us + mon->timeout_us)) {
        detected = FAILSAFE_HEARTBEAT_TIMEOUT;
    }
    // 3. Kiểm tra điện áp/dung lượng pin (< 10%)
    else if (!isfinite(mon->battery_remaining) || (mon->battery_remaining <= 1.0f && mon->battery_remaining < BATTERY_LOW_THRESHOLD_RATIO) ||
             (mon->battery_remaining > 1.0f && mon->battery_remaining < BATTERY_LOW_THRESHOLD_PCT)) {
        detected = FAILSAFE_BATTERY_LOW;
    }

    if (detected != FAILSAFE_NONE) {
        mon->is_triggered = true;
        mon->reason = detected;
        dispatch_emergency_command(mon, detected, x, y, z);
    }

    return mon->reason;
}

const char *failsafe_reason_to_str(failsafe_reason_t reason) {
    switch (reason) {
        case FAILSAFE_NONE:
            return "NORMAL_OPERATION";
        case FAILSAFE_HEARTBEAT_TIMEOUT:
            return "FAILSAFE_HEARTBEAT_TIMEOUT";
        case FAILSAFE_GEOFENCE_BREACH:
            return "FAILSAFE_GEOFENCE_BREACH";
        case FAILSAFE_BATTERY_LOW:
            return "FAILSAFE_BATTERY_LOW";
        case FAILSAFE_EMERGENCY_TRIGGER:
            return "FAILSAFE_EMERGENCY_TRIGGER";
        default:
            return "UNKNOWN_FAILSAFE_REASON";
    }
}

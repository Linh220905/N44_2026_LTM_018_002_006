#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
#include <math.h>
#include "../src/common/geofence.h"
#include "../src/agent/failsafe.h"

// Biến theo dõi lệnh MAVLink phát ra trong callback
static int g_action_callback_count = 0;
static failsafe_mavlink_cmd_t g_last_dispatched_cmd;

static void test_mavlink_callback(failsafe_monitor_t *mon, const failsafe_mavlink_cmd_t *cmd, void *user_data) {
    (void)mon;
    (void)user_data;
    g_action_callback_count++;
    if (cmd) {
        g_last_dispatched_cmd = *cmd;
    }
}

static void reset_callback_tracker(void) {
    g_action_callback_count = 0;
    g_last_dispatched_cmd.command = 0;
}

// Test Case 1: Giả lập thời gian trôi quá 1.5 giây không nhận Heartbeat -> Kích hoạt FAILSAFE_HEARTBEAT_TIMEOUT
static void test_heartbeat_timeout(void) {
    printf("[RUN ] Test Case 1: Heartbeat Timeout (> 1.5s)...\n");
    reset_callback_tracker();

    geofence_box_t box;
    geofence_box_init(&box, -50.0, 50.0, -50.0, 50.0, -50.0, 0.0);

    failsafe_monitor_t mon;
    failsafe_init(&mon, &box);
    failsafe_set_action_callback(&mon, test_mavlink_callback, NULL);

    uint64_t current_time_us = 1000000ULL; // t = 1.0s
    failsafe_update_heartbeat(&mon, current_time_us);
    failsafe_update_battery(&mon, 0.85f); // 85% pin

    // Kiểm tra trong điều kiện bình thường (thời gian trôi 500ms, vị trí an toàn)
    current_time_us += 500000ULL; // t = 1.5s (sau 500ms)
    failsafe_reason_t reason = failsafe_check(&mon, current_time_us, 0.0, 0.0, -10.0);
    assert(reason == FAILSAFE_NONE);
    assert(!mon.is_triggered);
    assert(g_action_callback_count == 0);

    // Giả lập trôi quá 1.5 giây kể từ Heartbeat cuối (1.0s + 1.6s = 2.6s)
    current_time_us = 1000000ULL + 1600000ULL; // trôi 1,600,000 us > 1,500,000 us
    reason = failsafe_check(&mon, current_time_us, 0.0, 0.0, -10.0);

    assert(reason == FAILSAFE_HEARTBEAT_TIMEOUT);
    assert(mon.is_triggered == true);
    assert(mon.reason == FAILSAFE_HEARTBEAT_TIMEOUT);
    assert(g_action_callback_count == 1);
    assert(g_last_dispatched_cmd.command == MAV_CMD_DO_SET_MODE);
    assert((int)g_last_dispatched_cmd.param1 == FLIGHT_MODE_AUTO_HOVER);

    printf("[PASS] Test Case 1 passed: FAILSAFE_HEARTBEAT_TIMEOUT triggered, MAVLink AUTO_HOVER sent.\n\n");
}

// Test Case 2: Truyền tọa độ vượt ngưỡng +/- 50 m -> Kích hoạt FAILSAFE_GEOFENCE_BREACH
static void test_geofence_breach(void) {
    printf("[RUN ] Test Case 2: Geofence Breach (Vượt ngưỡng +/- 50m)...\n");
    reset_callback_tracker();

    geofence_box_t box;
    // Ngưỡng không gian: X từ -50m đến +50m, Y từ -50m đến +50m, Z từ -50m (độ cao 50m) đến 0m (mặt đất)
    geofence_box_init(&box, -50.0, 50.0, -50.0, 50.0, -50.0, 0.0);

    // 2.1 Kiểm tra độc lập hàm geofence_is_breached
    assert(geofence_is_breached(&box, 0.0, 0.0, -20.0) == false);  // Trong vùng an toàn
    assert(geofence_is_breached(&box, 50.0, 50.0, -50.0) == false); // Ngay tại biên
    assert(geofence_is_breached(&box, 50.1, 0.0, -20.0) == true);   // Vượt X dương (+50.1m)
    assert(geofence_is_breached(&box, -50.5, 0.0, -20.0) == true);  // Vượt X âm (-50.5m)
    assert(geofence_is_breached(&box, 0.0, 55.0, -20.0) == true);   // Vượt Y dương (+55.0m)
    assert(geofence_is_breached(&box, 0.0, -51.0, -20.0) == true);  // Vượt Y âm (-51.0m)
    assert(geofence_is_breached(&box, 0.0, 0.0, -52.0) == true);   // Vượt Z trần cao (> 50m độ cao)
    assert(geofence_is_breached(&box, 0.0, 0.0, 5.0) == true);     // Vượt Z sàn (dưới đất)

    // 2.2 Kiểm tra tích hợp failsafe_check
    failsafe_monitor_t mon;
    failsafe_init(&mon, &box);
    failsafe_set_action_callback(&mon, test_mavlink_callback, NULL);

    uint64_t current_time_us = 2000000ULL;
    failsafe_update_heartbeat(&mon, current_time_us);
    failsafe_update_battery(&mon, 0.90f);

    // Drone bay vọt ra ngoài x = 55.0m (> 50.0m)
    failsafe_reason_t reason = failsafe_check(&mon, current_time_us + 10000ULL, 55.0, 10.0, -20.0);

    assert(reason == FAILSAFE_GEOFENCE_BREACH);
    assert(mon.is_triggered == true);
    assert(mon.reason == FAILSAFE_GEOFENCE_BREACH);
    assert(g_action_callback_count == 1);
    assert(g_last_dispatched_cmd.command == MAV_CMD_NAV_LAND);

    printf("[PASS] Test Case 2 passed: FAILSAFE_GEOFENCE_BREACH triggered, MAVLink MAV_CMD_NAV_LAND sent.\n\n");
}

// Test Case 3: Điện áp giảm dưới 10% -> Kích hoạt FAILSAFE_BATTERY_LOW
static void test_battery_low(void) {
    printf("[RUN ] Test Case 3: Battery Low (< 10%%)...\n");
    reset_callback_tracker();

    geofence_box_t box;
    geofence_box_init(&box, -50.0, 50.0, -50.0, 50.0, -50.0, 0.0);

    failsafe_monitor_t mon;
    failsafe_init(&mon, &box);
    failsafe_set_action_callback(&mon, test_mavlink_callback, NULL);

    uint64_t current_time_us = 3000000ULL;
    failsafe_update_heartbeat(&mon, current_time_us);

    // Thử mức pin 12% (> 10%) -> Vẫn an toàn
    failsafe_update_battery(&mon, 0.12f);
    failsafe_reason_t reason = failsafe_check(&mon, current_time_us + 50000ULL, 0.0, 0.0, -10.0);
    assert(reason == FAILSAFE_NONE);
    assert(!mon.is_triggered);
    assert(g_action_callback_count == 0);

    // Pin sụt xuống 8% (< 10%)
    failsafe_update_battery(&mon, 0.08f);
    reason = failsafe_check(&mon, current_time_us + 100000ULL, 0.0, 0.0, -10.0);

    assert(reason == FAILSAFE_BATTERY_LOW);
    assert(mon.is_triggered == true);
    assert(mon.reason == FAILSAFE_BATTERY_LOW);
    assert(g_action_callback_count == 1);
    assert(g_last_dispatched_cmd.command == MAV_CMD_NAV_LAND);

    printf("[PASS] Test Case 3 passed: FAILSAFE_BATTERY_LOW triggered, MAVLink MAV_CMD_NAV_LAND sent.\n\n");
}

// Test Case 4: Lệnh dừng khẩn cấp thủ công từ GCS
static void test_manual_emergency(void) {
    printf("[RUN ] Test Case 4: Manual Emergency Stop...\n");
    reset_callback_tracker();

    geofence_box_t box;
    geofence_box_init(&box, -50.0, 50.0, -50.0, 50.0, -50.0, 0.0);

    failsafe_monitor_t mon;
    failsafe_init(&mon, &box);
    failsafe_set_action_callback(&mon, test_mavlink_callback, NULL);

    failsafe_trigger_emergency(&mon);
    assert(mon.is_triggered == true);
    assert(mon.reason == FAILSAFE_EMERGENCY_TRIGGER);
    assert(g_action_callback_count == 1);
    assert(g_last_dispatched_cmd.command == MAV_CMD_NAV_LAND);

    printf("[PASS] Test Case 4 passed: Manual Emergency Kill confirmed.\n\n");
}

int main(void) {
    printf("==================================================\n");
    printf("  DRONE LIGHT SHOW - FAILSAFE & GEOFENCE TEST SUITE\n");
    printf("==================================================\n\n");

    geofence_box_t fence;
    geofence_box_init(&fence, -50, 50, -50, 50, -50, 0);
    assert(geofence_is_breached(&fence, NAN, 0, -2));
    assert(geofence_is_breached(&fence, 0, INFINITY, -2));
    geofence_box_init(&fence, 5, -5, -50, 50, -50, 0);
    assert(geofence_is_breached(&fence, 0, 0, -2));
    failsafe_monitor_t invalid_battery;
    failsafe_init(&invalid_battery, NULL);
    geofence_box_init(&invalid_battery.fence, -50, 50, -50, 50, -50, 0);
    failsafe_update_battery(&invalid_battery, NAN);
    assert(failsafe_check(&invalid_battery, 1, 0, 0, -2) == FAILSAFE_BATTERY_LOW);
    test_heartbeat_timeout();
    test_geofence_breach();
    test_battery_low();
    test_manual_emergency();

    printf("==================================================\n");
    printf("  ALL 4 TEST CASES COMPLETED SUCCESSFULLY! [OK]   \n");
    printf("==================================================\n");
    return 0;
}

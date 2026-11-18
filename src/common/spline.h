#ifndef SPLINE_H
#define SPLINE_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Điểm mốc quỹ đạo: thời điểm, vị trí và vận tốc mong muốn tại mốc.
 *
 * Tọa độ theo hệ NED giống src/common/geofence.h (z âm là độ cao).
 */
typedef struct {
    double t;          // thời gian (giây)
    double x, y, z;    // tọa độ mốc (m)
    double vx, vy, vz; // vận tốc mốc (m/s)
} waypoint_knot_t;

/**
 * @brief Nội suy vị trí 3D bằng Cubic Hermite Spline giữa hai mốc p0 -> p1.
 *
 * Đường cong đi qua đúng vị trí và đúng vận tốc của cả hai mốc, nên khi ghép
 * các đoạn liền nhau (đoạn sau dùng lại mốc cuối của đoạn trước) quỹ đạo liên
 * tục C1: vị trí và vận tốc không bị nhảy tại điểm nút.
 *
 * - t_curr trước p0->t (hoặc NaN): trả về vị trí p0; sau p1->t: vị trí p1.
 * - Đoạn suy biến (p1->t <= p0->t): trả về vị trí p0.
 * - Có con trỏ NULL: hàm không ghi gì.
 */
void spline_interpolate(const waypoint_knot_t *p0, const waypoint_knot_t *p1,
                        double t_curr, double *out_x, double *out_y, double *out_z);

/**
 * @brief Vận tốc (đạo hàm theo thời gian) của cùng đường cong tại t_curr.
 *
 * Tại p0->t trả về vận tốc p0, tại p1->t trả về vận tốc p1. Ngoài đoạn
 * [p0->t, p1->t] hoặc đoạn suy biến trả về 0, khớp với vị trí đứng yên ở trên.
 * Có con trỏ NULL: hàm không ghi gì.
 */
void spline_velocity(const waypoint_knot_t *p0, const waypoint_knot_t *p1,
                     double t_curr, double *out_vx, double *out_vy, double *out_vz);

#ifdef __cplusplus
}
#endif

#endif // SPLINE_H

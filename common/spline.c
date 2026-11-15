#include "spline.h"

#include <stddef.h>

/*
 * Cubic Hermite trên đoạn [t0, t1] với h = t1 - t0 và s = (t - t0) / h ∈ [0, 1]:
 *   p(s) = h00(s) p0 + h10(s) h v0 + h01(s) p1 + h11(s) h v1
 *   h00 = 2s^3 - 3s^2 + 1     h10 = s^3 - 2s^2 + s
 *   h01 = -2s^3 + 3s^2        h11 = s^3 - s^2
 * Vận tốc v được nhân với h vì đạo hàm theo s bằng h lần đạo hàm theo t.
 */
static double hermite(double s, double h, double p0, double v0, double p1, double v1) {
    double s2 = s * s, s3 = s2 * s;
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * h * v0 +
           (3 * s2 - 2 * s3) * p1 + (s3 - s2) * h * v1;
}

/* dp/dt = (dp/ds) / h. Tại s = 0 bằng v0, tại s = 1 bằng v1. */
static double hermite_rate(double s, double h, double p0, double v0, double p1, double v1) {
    double s2 = s * s;
    return (6 * s2 - 6 * s) * (p0 - p1) / h + (3 * s2 - 4 * s + 1) * v0 +
           (3 * s2 - 2 * s) * v1;
}

void spline_interpolate(const waypoint_knot_t *p0, const waypoint_knot_t *p1,
                        double t_curr, double *out_x, double *out_y, double *out_z) {
    if (!p0 || !p1 || !out_x || !out_y || !out_z) return;
    double h = p1->t - p0->t;
    /* Ngoài đoạn hoặc đoạn suy biến: drone giữ vị trí của mốc gần nhất. */
    const waypoint_knot_t *hold = NULL;
    if (!(h > 0.0) || !(t_curr > p0->t)) hold = p0;
    else if (t_curr >= p1->t) hold = p1;
    if (hold) {
        *out_x = hold->x;
        *out_y = hold->y;
        *out_z = hold->z;
        return;
    }
    double s = (t_curr - p0->t) / h;
    *out_x = hermite(s, h, p0->x, p0->vx, p1->x, p1->vx);
    *out_y = hermite(s, h, p0->y, p0->vy, p1->y, p1->vy);
    *out_z = hermite(s, h, p0->z, p0->vz, p1->z, p1->vz);
}

void spline_velocity(const waypoint_knot_t *p0, const waypoint_knot_t *p1,
                     double t_curr, double *out_vx, double *out_vy, double *out_vz) {
    if (!p0 || !p1 || !out_vx || !out_vy || !out_vz) return;
    double h = p1->t - p0->t;
    if (!(h > 0.0) || !(t_curr >= p0->t) || !(t_curr <= p1->t)) {
        *out_vx = *out_vy = *out_vz = 0.0;
        return;
    }
    double s = (t_curr - p0->t) / h;
    *out_vx = hermite_rate(s, h, p0->x, p0->vx, p1->x, p1->vx);
    *out_vy = hermite_rate(s, h, p0->y, p0->vy, p1->y, p1->vy);
    *out_vz = hermite_rate(s, h, p0->z, p0->vz, p1->z, p1->vz);
}

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "../common/spline.h"

static const double PI = 3.14159265358979323846;

static int near(double a, double b, double tol) { return fabs(a - b) <= tol; }

static waypoint_knot_t knot(double t, double x, double y, double z,
                            double vx, double vy, double vz) {
    return (waypoint_knot_t){t, x, y, z, vx, vy, vz};
}

// Vị trí và vận tốc của đoạn a -> b tại thời điểm t
static void eval(const waypoint_knot_t *a, const waypoint_knot_t *b, double t,
                 double p[3], double v[3]) {
    spline_interpolate(a, b, t, &p[0], &p[1], &p[2]);
    spline_velocity(a, b, t, &v[0], &v[1], &v[2]);
}

// Quỹ đạo nhiều đoạn: chọn đoạn chứa t rồi nội suy
static void path_eval(const waypoint_knot_t *k, int count, double t, double p[3], double v[3]) {
    int i = 0;
    while (i + 2 < count && t > k[i + 1].t) ++i;
    eval(&k[i], &k[i + 1], t, p, v);
}

// Test Case 1: Đường cong đi qua đúng vị trí và vận tốc của hai mốc
static void test_endpoints(void) {
    printf("[RUN ] Test Case 1: Khớp vị trí và vận tốc tại hai điểm mốc...\n");
    waypoint_knot_t a = knot(2.0, 1.0, -2.0, -5.0, 0.5, 1.0, -0.3);
    waypoint_knot_t b = knot(5.0, 4.0, 3.0, -9.0, -1.0, 0.2, 0.0);
    double p[3], v[3];

    eval(&a, &b, a.t, p, v);
    assert(p[0] == a.x && p[1] == a.y && p[2] == a.z);
    assert(near(v[0], a.vx, 1e-12) && near(v[1], a.vy, 1e-12) && near(v[2], a.vz, 1e-12));

    eval(&a, &b, b.t, p, v);
    assert(p[0] == b.x && p[1] == b.y && p[2] == b.z);
    assert(near(v[0], b.vx, 1e-12) && near(v[1], b.vy, 1e-12) && near(v[2], b.vz, 1e-12));

    // Ngay sát mốc nhưng vẫn trong đoạn: công thức Hermite cho cùng giá trị
    eval(&a, &b, a.t + 1e-9, p, v);
    assert(near(p[0], a.x, 1e-6) && near(p[1], a.y, 1e-6) && near(p[2], a.z, 1e-6));
    assert(near(v[0], a.vx, 1e-6) && near(v[1], a.vy, 1e-6) && near(v[2], a.vz, 1e-6));
    eval(&a, &b, b.t - 1e-9, p, v);
    assert(near(p[0], b.x, 1e-6) && near(p[1], b.y, 1e-6) && near(p[2], b.z, 1e-6));
    assert(near(v[0], b.vx, 1e-6) && near(v[1], b.vy, 1e-6) && near(v[2], b.vz, 1e-6));

    printf("[PASS] Test Case 1 passed: p(t0)=p0, p(t1)=p1, v(t0)=v0, v(t1)=v1.\n\n");
}

// Đa thức bậc 3 cho từng trục: f(t) = c0 + c1 t + c2 t^2 + c3 t^3
static const double C[3][4] = {{1.0, -2.0, 0.5, 0.25}, {-3.0, 1.5, -0.75, 0.1}, {-10.0, 0.0, 0.4, -0.05}};
static double cubic(int axis, double t) {
    const double *c = C[axis];
    return c[0] + t * (c[1] + t * (c[2] + t * c[3]));
}
static double cubic_rate(int axis, double t) {
    const double *c = C[axis];
    return c[1] + t * (2 * c[2] + 3 * t * c[3]);
}
static waypoint_knot_t cubic_knot(double t) {
    return knot(t, cubic(0, t), cubic(1, t), cubic(2, t),
                cubic_rate(0, t), cubic_rate(1, t), cubic_rate(2, t));
}

// Test Case 2: Quỹ đạo thật là đa thức bậc 3 -> Hermite phải tái tạo chính xác trên t0 -> t1
static void test_cubic_exact(void) {
    printf("[RUN ] Test Case 2: Sai số nội suy với quỹ đạo bậc 3 khi t chạy t0 -> t1...\n");
    waypoint_knot_t a = cubic_knot(1.0), b = cubic_knot(4.0);
    double max_pos = 0.0, max_vel = 0.0, p[3], v[3];
    for (int i = 0; i <= 1000; ++i) {
        double t = a.t + (b.t - a.t) * i / 1000.0;
        eval(&a, &b, t, p, v);
        for (int k = 0; k < 3; ++k) {
            max_pos = fmax(max_pos, fabs(p[k] - cubic(k, t)));
            max_vel = fmax(max_vel, fabs(v[k] - cubic_rate(k, t)));
        }
    }
    printf("       sai số lớn nhất: vị trí %.2e m, vận tốc %.2e m/s\n", max_pos, max_vel);
    assert(max_pos < 1e-9 && max_vel < 1e-9);
    printf("[PASS] Test Case 2 passed: tái tạo chính xác quỹ đạo bậc 3.\n\n");
}

// Quỹ đạo tròn nghiêng: x = R cos(wt), y = R sin(wt), z = Z0 + A sin(wt)
#define CIRCLE_R 8.0
#define CIRCLE_W 0.5
#define CIRCLE_Z0 (-15.0)
#define CIRCLE_A 2.0
static waypoint_knot_t circle_knot(double t) {
    double c = cos(CIRCLE_W * t), s = sin(CIRCLE_W * t);
    return knot(t, CIRCLE_R * c, CIRCLE_R * s, CIRCLE_Z0 + CIRCLE_A * s,
                -CIRCLE_R * CIRCLE_W * s, CIRCLE_R * CIRCLE_W * c, CIRCLE_A * CIRCLE_W * c);
}
// Sai số lớn nhất (m) so với quỹ đạo thật khi đặt mốc cách nhau h giây, trên một chu kỳ
static double circle_error(double h) {
    int segments = (int)lround(2 * PI / CIRCLE_W / h);
    double worst = 0.0, p[3], v[3];
    for (int k = 0; k < segments; ++k) {
        waypoint_knot_t a = circle_knot(k * h), b = circle_knot((k + 1) * h);
        for (int i = 0; i <= 200; ++i) {
            double t = a.t + h * i / 200.0;
            waypoint_knot_t exact = circle_knot(t);
            eval(&a, &b, t, p, v);
            worst = fmax(worst, hypot(hypot(p[0] - exact.x, p[1] - exact.y), p[2] - exact.z));
        }
    }
    return worst;
}

// Test Case 3: Quỹ đạo cong (không phải đa thức): sai số nằm trong cận lý thuyết h^4/384 * max|f''''|
static void test_error_bound(void) {
    printf("[RUN ] Test Case 3: Sai số nội suy quỹ đạo tròn theo khoảng cách mốc h...\n");
    double w4 = pow(CIRCLE_W, 4);
    double scale = w4 / 384.0 * sqrt(2 * CIRCLE_R * CIRCLE_R + CIRCLE_A * CIRCLE_A);
    double e1 = circle_error(1.0), e2 = circle_error(0.5);
    printf("       h=1.0s: %.3e m (cận %.3e) | h=0.5s: %.3e m (cận %.3e) | tỉ lệ %.1f\n",
           e1, scale, e2, scale / 16.0, e1 / e2);
    assert(e1 <= scale && e2 <= scale / 16.0);
    assert(e1 / e2 > 12.0 && e1 / e2 < 20.0); // hội tụ bậc 4: giảm h một nửa -> sai số giảm ~16 lần
    printf("[PASS] Test Case 3 passed: sai số trong cận và hội tụ bậc O(h^4).\n\n");
}

// Test Case 4: Ghép hai đoạn qua một mốc -> vị trí và vận tốc liên tục (C1)
static void test_c1_continuity(void) {
    printf("[RUN ] Test Case 4: Tính liên tục C1 tại điểm nút giữa hai đoạn...\n");
    waypoint_knot_t k0 = knot(0.0, 0.0, 0.0, -5.0, 0.0, 0.0, 0.0);
    waypoint_knot_t k1 = knot(2.0, 4.0, 1.0, -8.0, 1.5, -0.5, -0.8);
    waypoint_knot_t k2 = knot(5.0, 6.0, 6.0, -6.0, 0.0, 0.0, 0.0);
    double pl[3], vl[3], pr[3], vr[3], eps = 1e-7;
    eval(&k0, &k1, k1.t - eps, pl, vl); // giới hạn trái
    eval(&k1, &k2, k1.t + eps, pr, vr); // giới hạn phải
    double knot_v[3] = {k1.vx, k1.vy, k1.vz};
    for (int k = 0; k < 3; ++k) {
        assert(near(pl[k], pr[k], 1e-5));
        assert(near(vl[k], vr[k], 1e-5));
        assert(near(vl[k], knot_v[k], 1e-5));
    }

    // spline_velocity phải đúng là đạo hàm của spline_interpolate (so với sai phân trung tâm)
    const waypoint_knot_t *seg[2][2] = {{&k0, &k1}, {&k1, &k2}};
    double delta = 1e-5, worst = 0.0;
    for (int s = 0; s < 2; ++s) {
        const waypoint_knot_t *a = seg[s][0], *b = seg[s][1];
        for (int i = 1; i < 100; ++i) {
            double t = a->t + (b->t - a->t) * i / 100.0, p0[3], p1[3], v[3], unused[3];
            eval(a, b, t - delta, p0, unused);
            eval(a, b, t + delta, p1, unused);
            eval(a, b, t, unused, v);
            for (int k = 0; k < 3; ++k)
                worst = fmax(worst, fabs((p1[k] - p0[k]) / (2 * delta) - v[k]));
        }
    }
    printf("       lệch vận tốc trái/phải tại nút: %.2e m/s, lệch so với đạo hàm số: %.2e m/s\n",
           fmax(fmax(fabs(vl[0] - vr[0]), fabs(vl[1] - vr[1])), fabs(vl[2] - vr[2])), worst);
    assert(worst < 1e-6);
    printf("[PASS] Test Case 4 passed: vị trí và vận tốc liên tục tại điểm nút.\n\n");
}

// Test Case 5: Quỹ đạo nhiều đoạn (vận tốc mốc kiểu Catmull-Rom) không bị giật tại các nút
static void test_multi_segment_smooth(void) {
    printf("[RUN ] Test Case 5: Quỹ đạo 4 đoạn không giật vận tốc tại các điểm nút...\n");
    double pos[5][3] = {{0, 0, -5}, {5, 0, -5}, {5, 5, -8}, {0, 5, -8}, {0, 0, -5}};
    waypoint_knot_t path[5];
    for (int i = 0; i < 5; ++i) {
        double v[3] = {0, 0, 0};
        if (i > 0 && i < 4)
            for (int k = 0; k < 3; ++k) v[k] = (pos[i + 1][k] - pos[i - 1][k]) / 6.0;
        path[i] = knot(3.0 * i, pos[i][0], pos[i][1], pos[i][2], v[0], v[1], v[2]);
    }
    double dt = 1e-3, prev_p[3], prev_v[3], p[3], v[3], max_dv = 0.0, max_speed = 0.0;
    path_eval(path, 5, 0.0, prev_p, prev_v);
    for (int i = 1; i <= 12000; ++i) {
        path_eval(path, 5, i * dt, p, v);
        double dp = hypot(hypot(p[0] - prev_p[0], p[1] - prev_p[1]), p[2] - prev_p[2]);
        double dv = hypot(hypot(v[0] - prev_v[0], v[1] - prev_v[1]), v[2] - prev_v[2]);
        double speed = hypot(hypot(v[0], v[1]), v[2]);
        assert(dp <= fmax(speed, hypot(hypot(prev_v[0], prev_v[1]), prev_v[2])) * dt + 1e-6);
        max_dv = fmax(max_dv, dv);
        max_speed = fmax(max_speed, speed);
        for (int k = 0; k < 3; ++k) { prev_p[k] = p[k]; prev_v[k] = v[k]; }
    }
    printf("       tốc độ lớn nhất %.2f m/s, bước nhảy vận tốc lớn nhất %.4f m/s mỗi 1 ms (gia tốc ~%.1f m/s^2)\n",
           max_speed, max_dv, max_dv / dt);
    assert(max_dv < 0.02); // gia tốc < 20 m/s^2, không có điểm vận tốc nhảy bậc
    assert(prev_p[0] == 0.0 && prev_p[1] == 0.0 && prev_p[2] == -5.0);
    printf("[PASS] Test Case 5 passed: chuyển tiếp mượt qua mọi điểm nút.\n\n");
}

// Test Case 6: Hai mốc vận tốc 0 -> bay thẳng, không vọt lố (dùng khi chuyển đội hình)
static void test_rest_to_rest(void) {
    printf("[RUN ] Test Case 6: Mốc đứng yên -> đường thẳng, không vọt lố...\n");
    waypoint_knot_t a = knot(0.0, 1.0, 2.0, -3.0, 0, 0, 0), b = knot(4.0, 7.0, -2.0, -9.0, 0, 0, 0);
    double d[3] = {b.x - a.x, b.y - a.y, b.z - a.z}, start[3] = {a.x, a.y, a.z}, last = 0.0;
    for (int i = 0; i <= 400; ++i) {
        double p[3], v[3];
        eval(&a, &b, a.t + (b.t - a.t) * i / 400.0, p, v);
        double ratio = (p[0] - start[0]) / d[0];
        for (int k = 1; k < 3; ++k) assert(near((p[k] - start[k]) / d[k], ratio, 1e-12));
        assert(ratio >= last - 1e-12 && ratio <= 1.0 + 1e-12);
        last = ratio;
    }
    printf("[PASS] Test Case 6 passed: đi thẳng từ p0 tới p1, tiến đều không quay đầu.\n\n");
}

// Test Case 7: Ngoài đoạn, đoạn suy biến, NaN và con trỏ NULL
static void test_edge_cases(void) {
    printf("[RUN ] Test Case 7: Biên thời gian, đoạn suy biến, NaN, NULL...\n");
    waypoint_knot_t a = knot(1.0, 1.0, 2.0, -3.0, 1.0, 1.0, 1.0), b = knot(3.0, 4.0, 5.0, -6.0, 2.0, 2.0, 2.0);
    double p[3], v[3];

    eval(&a, &b, 0.0, p, v); // trước t0: giữ p0, đứng yên
    assert(p[0] == a.x && p[1] == a.y && p[2] == a.z && v[0] == 0 && v[1] == 0 && v[2] == 0);
    eval(&a, &b, 9.0, p, v); // sau t1: giữ p1, đứng yên
    assert(p[0] == b.x && p[1] == b.y && p[2] == b.z && v[0] == 0 && v[1] == 0 && v[2] == 0);
    eval(&a, &b, NAN, p, v);
    assert(p[0] == a.x && p[1] == a.y && p[2] == a.z && v[0] == 0 && v[1] == 0 && v[2] == 0);

    waypoint_knot_t same_time = b;
    same_time.t = a.t;
    eval(&a, &same_time, a.t, p, v); // t1 == t0: không chia cho 0
    assert(p[0] == a.x && p[1] == a.y && p[2] == a.z && v[0] == 0 && v[1] == 0 && v[2] == 0);
    eval(&a, &same_time, a.t + 0.5, p, v); // t1 == t0, t sau mốc: vẫn giữ p0
    assert(p[0] == a.x && p[1] == a.y && p[2] == a.z && v[0] == 0 && v[1] == 0 && v[2] == 0);
    eval(&b, &a, 2.0, p, v);         // t1 < t0
    assert(p[0] == b.x && p[1] == b.y && p[2] == b.z && v[0] == 0 && v[1] == 0 && v[2] == 0);
    eval(&b, &a, 5.0, p, v);         // t1 < t0, t sau cả hai mốc: vẫn giữ p0
    assert(p[0] == b.x && p[1] == b.y && p[2] == b.z && v[0] == 0 && v[1] == 0 && v[2] == 0);

    double x = 42.0, y = 42.0, z = 42.0;
    spline_interpolate(NULL, &b, 2.0, &x, &y, &z);
    spline_interpolate(&a, &b, 2.0, &x, NULL, &z);
    spline_velocity(&a, NULL, 2.0, &x, &y, &z);
    spline_velocity(&a, &b, 2.0, NULL, &y, &z);
    assert(x == 42.0 && y == 42.0 && z == 42.0);

    printf("[PASS] Test Case 7 passed: không chia cho 0, không ghi khi gặp NULL.\n\n");
}

int main(void) {
    printf("=== BẮT ĐẦU UNIT TEST: TRAJECTORY SPLINE ENGINE (CUBIC HERMITE C1) ===\n\n");
    test_endpoints();
    test_cubic_exact();
    test_error_bound();
    test_c1_continuity();
    test_multi_segment_smooth();
    test_rest_to_rest();
    test_edge_cases();
    printf("=== TẤT CẢ TEST SPLINE ĐÃ VƯỢT QUA THÀNH CÔNG ===\n");
    return 0;
}

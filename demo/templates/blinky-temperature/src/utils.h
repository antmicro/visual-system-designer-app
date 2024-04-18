#ifndef APP_UTILS_H
#define APP_UTILS_H

#include <zephyr/drivers/gpio.h>

struct led {
	struct gpio_dt_spec gpio;
	const char *name;
	bool state;
};

struct thermometer {
	const struct device *dev;
	const char *name;
};

int init_led(struct led *led);
int init_thermometer(struct thermometer *thermometer);

int toggle_led_state(struct led *led);
double get_temperature(struct thermometer *thermometer);
int print_temperature(const struct device *thermoemeter);

#endif /* APP_UTILS_H */

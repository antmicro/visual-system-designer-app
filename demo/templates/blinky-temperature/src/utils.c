#include <math.h>

#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>

#include "utils.h"

static int read_temperature(const struct device *dev, struct sensor_value *val)
{
	int ret;

	ret = sensor_sample_fetch_chan(dev, SENSOR_CHAN_AMBIENT_TEMP);
	if (ret < 0) {
		printf("Could not fetch temperature: %d\n", ret);
		return ret;
	}

	ret = sensor_channel_get(dev, SENSOR_CHAN_AMBIENT_TEMP, val);
	if (ret < 0) {
		printf("Could not get temperature: %d\n", ret);
	}
	return ret;
}

int print_temperature(const struct device *thermoemeter)
{
	int ret;
	struct sensor_value value;

	ret = read_temperature(thermoemeter, &value);
	if (ret != 0) {
		printf("Failed to read temperature: %d\n", ret);
		return -1;
	}
	printf("%s: %0.1lf°C\n", thermoemeter->name, sensor_value_to_double(&value));
	return 0;
}

int init_led(struct led *led)
{
	int ret;

	printf("Discovered LED: %s\n", led->name);

	if (!gpio_is_ready_dt(&led->gpio)) {
		printf("LED %s is not ready\n", led->name);
		return -1;
	}

	ret = gpio_pin_configure_dt(&led->gpio, GPIO_OUTPUT_ACTIVE);
	if (ret < 0) {
		printf("Failed to configure LED %s\n", led->name);
		return ret;
	}

	led->state = false;
	return 0;
}

int init_thermometer(struct thermometer *thermometer)
{
	printf("Discovered thermometer: %s\n", thermometer->name);

	if (!device_is_ready(thermometer->dev)) {
		printf("Device %s is not ready\n", thermometer->name);
		return -1;
	}
	return 0;
}

inline double get_temperature(struct thermometer *thermometer)
{
	int ret;
	struct sensor_value value;

	ret = read_temperature(thermometer->dev, &value);
	if (ret != 0) {
		printf("failed to read temperature: %d\n", ret);
		return NAN;
	}

	return sensor_value_to_double(&value);
}

inline int toggle_led_state(struct led *led)
{
	int ret;

	ret = gpio_pin_toggle_dt(&led->gpio);
	if (ret < 0) {
		printf("Failed to toggle LED %s state\n", led->name);
		return ret;
	}

	led->state = !led->state;

	printk("LED %s state: %d\n", led->name, led->state);
	return 0;
}

/*
 * Copyright (c) 2016 ARM Ltd.
 * Copyright (c) 2023 FTP Technologies
 * Copyright (c) 2023 Daniel DeGrasse <daniel@degrasse.com>
 * Copyright (c) 2023 Antmicro <www.antmicro.com>
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/gpio.h>

static double high_temp;
static double low_temp;

#define GET_GPIO_SPEC(n) GPIO_DT_SPEC_GET(n, gpios),
#define GET_NAME(n) DT_NODE_FULL_NAME(n),

#define SENSOR_DEVICE_ELEM(n) DEVICE_DT_GET(n),
#define SENSOR_NAME_ELEM(n) DT_PROP(n, friendly_name),

#define IS_SENSOR(n) DT_NODE_HAS_PROP(n, friendly_name)

#define GET_SENSOR_DEVICE(n) \
	COND_CODE_1(DT_NODE_HAS_PROP(n, friendly_name), (SENSOR_DEVICE_ELEM(n)), ())

#define GET_SENSOR_NAME(n) \
	COND_CODE_1(DT_NODE_HAS_PROP(n, friendly_name), (SENSOR_NAME_ELEM(n)), ())


static const struct gpio_dt_spec leds[] = {
	DT_FOREACH_CHILD(DT_PATH(leds), GET_GPIO_SPEC)
};

static const char *led_names[] = {
	DT_FOREACH_CHILD(DT_PATH(leds), GET_NAME)
};

static const struct device *const all_sensor_devices[] = {
	DT_FOREACH_NODE(GET_SENSOR_DEVICE)
};

static const char *all_sensor_names[] = {
	DT_FOREACH_NODE(GET_SENSOR_NAME)
};

static char is_themometer[ARRAY_SIZE(all_sensor_devices)];
static bool led_state[ARRAY_SIZE(leds)];

int read_temperature(const struct device *dev, struct sensor_value *val)
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

void temp_alert_handler(const struct device *dev, const struct sensor_trigger *trig)
{
	int ret;
	struct sensor_value value;
	double temp;

	/* Read sensor value */
	ret = read_temperature(dev, &value);
	if (ret < 0) {
		printf("Reading temperature failed: %d\n", ret);
		return;
	}
	temp = sensor_value_to_double(&value);
	if (temp <= low_temp) {
		printf("Temperature below threshold: %0.1f°C\n", temp);
	} else if (temp >= high_temp) {
		printf("Temperature above threshold: %0.1f°C\n", temp);
	} else {
		printf("Error: temperature alert triggered without valid condition\n");
	}
}

int main(void)
{
	struct sensor_value value;
	double temp;
	int ret;
	const struct sensor_trigger trig = {
		.chan = SENSOR_CHAN_AMBIENT_TEMP,
		.type = SENSOR_TRIG_THRESHOLD,
	};

	printf("Blinky and temperature example (%s)\n", CONFIG_ARCH);
	printf("LEDs registered: %d\n", ARRAY_SIZE(leds));
	printf("Sensors registered: %d\n", ARRAY_SIZE(all_sensor_devices));

	for (int i = 0; i < ARRAY_SIZE(leds); i++) {
		const struct gpio_dt_spec *led = &leds[i];
		if (!gpio_is_ready_dt(led)) {
			printf("LED %s is not ready\n", led_names[i]);
			return 0;
		}

		ret = gpio_pin_configure_dt(led, GPIO_OUTPUT_ACTIVE);
		if (ret < 0) {
			printf("Failed to configure LED %s\n", led_names[i]);
			return 0;
		}
		led_state[i] = true;
	}

	for (int i = 0; i < ARRAY_SIZE(all_sensor_devices); i++) {
		const struct device *const dev = all_sensor_devices[i];
		if (strcmp(all_sensor_names[i], "thermometer") == 0) {
			printf("Found thermometer: %s (dev address: %p)\n", dev->name, dev);
			is_themometer[i] = 1;
		}
		if (!device_is_ready(dev)) {
			printf("Device %s is not ready\n", dev->name);
			return 0;
		}

		/* First, fetch a sensor sample to use for sensor thresholds */
		ret = read_temperature(dev, &value);
		if (ret != 0) {
			printf("Failed to read temperature: %d\n", ret);
			return ret;
		}
		temp = sensor_value_to_double(&value);

		/* Set thresholds to +0.5 and +1.5 °C from ambient */
		low_temp = temp + 0.5;
		ret = sensor_value_from_double(&value, low_temp);
		if (ret != 0) {
			printf("Failed to convert low threshold to sensor value: %d\n", ret);
			return ret;
		}
		ret = sensor_attr_set(dev, SENSOR_CHAN_AMBIENT_TEMP,
							SENSOR_ATTR_LOWER_THRESH, &value);
		if (ret == 0) {
			/* This sensor supports threshold triggers */
			printf("Set temperature lower limit to %0.1f°C\n", low_temp);
		}

		high_temp = temp + 1.5;
		ret = sensor_value_from_double(&value, high_temp);
		if (ret != 0) {
			printf("Failed to convert low threshold to sensor value: %d\n", ret);
			return ret;
		}
		ret = sensor_attr_set(dev, SENSOR_CHAN_AMBIENT_TEMP,
							SENSOR_ATTR_UPPER_THRESH, &value);
		if (ret == 0) {
			/* This sensor supports threshold triggers */
			printf("Set temperature upper limit to %0.1f°C\n", high_temp);
		}

		ret = sensor_trigger_set(dev, &trig, temp_alert_handler);
		if (ret == 0) {
			printf("Enabled sensor threshold triggers\n");
		}
	}

	while (1) {
		for (int i = 0; i < ARRAY_SIZE(all_sensor_devices); i++) {
			const struct device *const dev = all_sensor_devices[i];
			if (!is_themometer[i]) {
				continue;
			}
			ret = read_temperature(dev, &value);
			if (ret != 0) {
				printf("Failed to read temperature: %d\n", ret);
				break;
			}
			printf("%s: %0.1lf°C\n", dev->name, sensor_value_to_double(&value));
		}

		for (int i = 0; i < ARRAY_SIZE(leds); i++) {
			const struct gpio_dt_spec *led = &leds[i];
			ret = gpio_pin_toggle_dt(led);
			if (ret < 0) {
				printf("Failed to toggle LED %s state\n", led_names[i]);
			}

			/* Update led state */
			led_state[i] = !led_state[i];

			printk("LED %s state: %d\n", led_names[i], led_state[i]);
		}

		k_sleep(K_MSEC(1000));
	}
	return 0;
}

/*
 * Generated file.
 */

#include <zephyr/kernel.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/devicetree.h>

#include <math.h>

#include "utils.h"

/* Dts labels of used nodes */

//! for label in all_labels
#define __{{ label.upper() }}_NODE DT_NODELABEL({{ label }})
//! endfor

/* Initialize structures for discovered nodes */

//! for led_name in leds
struct led {{ led_name }} = {
	.gpio = GPIO_DT_SPEC_GET(__{{ led_name.upper() }}_NODE, gpios),
	.name = DT_NODE_FULL_NAME(__{{ led_name.upper() }}_NODE),
};
//! endfor

//! for thermometer_name in thermometers
struct thermometer {{ thermometer_name }} = {
	.dev = DEVICE_DT_GET(__{{ thermometer_name.upper() }}_NODE),
	.name = DT_NODE_FULL_NAME(__{{ thermometer_name.upper() }}_NODE),
};
//! endfor

int main(void)
{
	int ret;
	double temp;

	/* Structures for nodes used in the demo */

//! for led_name in leds
	ret = init_led(&{{ led_name }});
	if (ret < 0) {
		return ret;
	}
//! endfor

//! for thermometer_name in thermometers
	ret = init_thermometer(&{{ thermometer_name }});
	if (ret < 0) {
		return ret;
	}
//! endfor

	while (1) {
		/* Actions for each node */

//! for led_name in leds
		ret = toggle_led_state(&{{ led_name }});
		if (ret < 0) {
			return ret;
		}
//! endfor

//! for thermometer_name in thermometers
		temp = get_temperature(&{{ thermometer_name }});
		if (isnan(temp)) {
			return -1;
		}
		printf("%s: %0.1lf°C\n", {{ thermometer_name }}.name, temp);
//! endfor

		k_sleep(K_MSEC(1000));
	}
	return 0;
}

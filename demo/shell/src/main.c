/*
 * Copyright (c) 2023 Antmicro <www.antmicro.com>
 * SPDX-License-Identifier: Apache-2.0
 */
#include <stdio.h>

int main(void)
{
	printf("Hello on %s", CONFIG_BOARD);
	return 0;
}

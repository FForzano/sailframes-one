/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <string.h>
#include <stdio.h>
/* USER CODE END Includes */

/* USER CODE BEGIN Defines */
#define ADC_BUFFER_SIZE 1000    // Number of ADC samples to capture
#define BURST_PULSES    8       // Number of 40kHz pulses to send
#define BURST_PERIOD_US 25      // Period of one 40kHz cycle in microseconds
#define PRE_CAPTURE_DELAY_US 50 // Delay after burst before sampling (transducer ringdown)
#define SAMPLE_RATE_HZ   1335940u // Measured 2026-05-09 via PA1 GPIO-toggle probe
#define BLANKING_SAMPLES 67       // Skip first ~50 µs of capture (TX feedthrough + RX ringup)
#define ECHO_THRESHOLD   100      // ADC counts (~80 mV) for threshold-based "echo start"
#define ZC_HALF_COUNT    3        // ZCs taken on each side of peak; 6 total averaged
/* USER CODE END Defines */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
ADC_HandleTypeDef hadc1;

TIM_HandleTypeDef htim2;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
uint16_t adc_buffer[ADC_BUFFER_SIZE];  // Buffer for captured ADC samples
volatile uint32_t capture_complete = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_TIM2_Init(void);
static void MX_ADC1_Init(void);
/* USER CODE BEGIN PFP */
typedef struct {
    int   peak_idx;         // sample index of envelope peak (max |sample - mean|)
    int   peak_amplitude;   // max |sample - mean|, ADC counts
    int   echo_start_idx;   // first post-blanking sample exceeding ECHO_THRESHOLD; -1 if none
    float dc_mean;          // mean ADC value across the buffer
    int   zc_count;         // number of ZCs averaged (target 2*ZC_HALF_COUNT, fewer if buffer edge)
    float zc_avg_idx;       // averaged sub-sample crossing index; ToF = zc_avg_idx / SAMPLE_RATE_HZ
} echo_analysis_t;

void send_burst(uint8_t num_pulses);
void capture_echo(void);
void send_samples_uart(void);
void delay_us(uint32_t us);
echo_analysis_t analyze_echo(uint16_t *buf, int n);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_TIM2_Init();
  MX_ADC1_Init();
  /* USER CODE BEGIN 2 */
  // Enable DWT cycle counter for microsecond delays
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
  DWT->CYCCNT = 0;
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

  // Calibrate ADC
  HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);

  // Send startup message
  char startup_msg[] = "\r\n=== Ultrasonic Burst Mode ===\r\n";
  HAL_UART_Transmit(&huart2, (uint8_t*)startup_msg, strlen(startup_msg), 100);
  char info_msg[100];
  sprintf(info_msg, "Burst: %d pulses @ 40kHz (%d us)\r\n", BURST_PULSES, BURST_PULSES * BURST_PERIOD_US);
  HAL_UART_Transmit(&huart2, (uint8_t*)info_msg, strlen(info_msg), 100);
  sprintf(info_msg, "Pre-capture delay: %d us\r\n", PRE_CAPTURE_DELAY_US);
  HAL_UART_Transmit(&huart2, (uint8_t*)info_msg, strlen(info_msg), 100);
  sprintf(info_msg, "Buffer: %d samples @ ~1.3 MHz (~%d us window)\r\n", ADC_BUFFER_SIZE, (int)(ADC_BUFFER_SIZE * 0.75));
  HAL_UART_Transmit(&huart2, (uint8_t*)info_msg, strlen(info_msg), 100);

  // Don't start continuous PWM - we'll send bursts instead
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */

    // Toggle LED to show activity
    HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);

    // Send burst of ultrasonic pulses
    send_burst(BURST_PULSES);

    // Brief delay for transducer ringdown before capturing
    delay_us(PRE_CAPTURE_DELAY_US);

    // Capture echo response
    capture_echo();

    // Analyze echo in firmware (Layer 1 + Layer 2): emit summary line BEFORE
    // the raw samples. Times use integer math in tenths-of-µs (Layer 1) and
    // nanoseconds (Layer 2 ZC) to avoid enabling float printf in newlib-nano.
    echo_analysis_t echo = analyze_echo(adc_buffer, ADC_BUFFER_SIZE);
    unsigned int peak_tus = (unsigned int)(
        (uint64_t)echo.peak_idx * 10000000ULL / SAMPLE_RATE_HZ);
    unsigned int dc_x10 = (unsigned int)(echo.dc_mean * 10.0f + 0.5f);
    unsigned int zc_tof_ns = (unsigned int)(
        echo.zc_avg_idx * 1.0e9f / (float)SAMPLE_RATE_HZ + 0.5f);
    char echo_msg[200];
    if (echo.echo_start_idx >= 0) {
        unsigned int start_tus = (unsigned int)(
            (uint64_t)echo.echo_start_idx * 10000000ULL / SAMPLE_RATE_HZ);
        sprintf(echo_msg,
            "ECHO: start=%d (%u.%u us) peak=%d (%u.%u us) zc[%d]=%u.%03u us amp=%d mean=%u.%u\r\n",
            echo.echo_start_idx, start_tus / 10, start_tus % 10,
            echo.peak_idx,        peak_tus  / 10, peak_tus  % 10,
            echo.zc_count,        zc_tof_ns / 1000, zc_tof_ns % 1000,
            echo.peak_amplitude,
            dc_x10 / 10, dc_x10 % 10);
    } else {
        sprintf(echo_msg,
            "ECHO: no_threshold_cross peak=%d (%u.%u us) zc[%d]=%u.%03u us amp=%d mean=%u.%u\r\n",
            echo.peak_idx, peak_tus / 10, peak_tus % 10,
            echo.zc_count, zc_tof_ns / 1000, zc_tof_ns % 1000,
            echo.peak_amplitude,
            dc_x10 / 10, dc_x10 % 10);
    }
    HAL_UART_Transmit(&huart2, (uint8_t*)echo_msg, strlen(echo_msg), 100);

    // Send captured data over UART
    send_samples_uart();

    // Wait before next capture (allows serial transmission to complete)
    HAL_Delay(1000);

  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 1;
  RCC_OscInitStruct.PLL.PLLN = 10;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV7;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief ADC1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC1_Init(void)
{

  /* USER CODE BEGIN ADC1_Init 0 */

  /* USER CODE END ADC1_Init 0 */

  ADC_MultiModeTypeDef multimode = {0};
  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC1_Init 1 */

  /* USER CODE END ADC1_Init 1 */

  /** Common config
  */
  hadc1.Instance = ADC1;
  hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
  hadc1.Init.Resolution = ADC_RESOLUTION_12B;
  hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc1.Init.ScanConvMode = ADC_SCAN_DISABLE;
  hadc1.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  hadc1.Init.LowPowerAutoWait = DISABLE;
  hadc1.Init.ContinuousConvMode = ENABLE;
  hadc1.Init.NbrOfConversion = 1;
  hadc1.Init.DiscontinuousConvMode = DISABLE;
  hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  hadc1.Init.DMAContinuousRequests = DISABLE;
  hadc1.Init.Overrun = ADC_OVR_DATA_PRESERVED;
  hadc1.Init.OversamplingMode = DISABLE;
  if (HAL_ADC_Init(&hadc1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure the ADC multi-mode
  */
  multimode.Mode = ADC_MODE_INDEPENDENT;
  if (HAL_ADCEx_MultiModeConfigChannel(&hadc1, &multimode) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_15;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SamplingTime = ADC_SAMPLETIME_2CYCLES_5;
  sConfig.SingleDiff = ADC_SINGLE_ENDED;
  sConfig.OffsetNumber = ADC_OFFSET_NONE;
  sConfig.Offset = 0;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC1_Init 2 */

  /* USER CODE END ADC1_Init 2 */

}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 0;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 1999;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 1000;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */
  HAL_TIM_MspPostInit(&htim2);

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  huart2.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart2.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : LD2_Pin */
  GPIO_InitStruct.Pin = LD2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LD2_GPIO_Port, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */
  // Sample-rate calibration probe on PA1 (= Nucleo CN8 / A1).
  // capture_echo() toggles this pin once per ADC sample. Scope it,
  // read frequency f, then real sample rate = 2 * f.
  {
    GPIO_InitTypeDef sr_probe = {0};
    sr_probe.Pin   = GPIO_PIN_1;
    sr_probe.Mode  = GPIO_MODE_OUTPUT_PP;
    sr_probe.Pull  = GPIO_NOPULL;
    sr_probe.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    HAL_GPIO_Init(GPIOA, &sr_probe);
  }
  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/**
 * @brief Microsecond delay using DWT cycle counter
 * @param us: microseconds to delay
 */
void delay_us(uint32_t us) {
    // At 80MHz, 1us = 80 cycles
    uint32_t start = DWT->CYCCNT;
    uint32_t cycles = us * 80;
    while ((DWT->CYCCNT - start) < cycles);
}

/**
 * @brief Send a burst of N pulses at 40kHz
 * @param num_pulses: number of pulses to send
 */
void send_burst(uint8_t num_pulses) {
    // Start PWM
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);

    // Wait for N complete periods (25us each at 40kHz)
    delay_us(num_pulses * BURST_PERIOD_US);

    // Stop PWM and force output low
    HAL_TIM_PWM_Stop(&htim2, TIM_CHANNEL_1);
}

/**
 * @brief Capture ADC samples as fast as possible into buffer
 * Uses direct register access for maximum speed (~1MHz sampling)
 * ADC is configured for continuous conversion mode
 */
void capture_echo(void) {
    // Start continuous conversion
    HAL_ADC_Start(&hadc1);

    // Fast sampling loop using direct register access
    // Wait for first conversion, then read as fast as possible
    // At 80MHz/4 ADC clock with 15 cycle conversion = ~1.33MHz max rate
    for (int i = 0; i < ADC_BUFFER_SIZE; i++) {
        // Wait for end of conversion (EOC flag)
        while (!(ADC1->ISR & ADC_ISR_EOC));
        // Read data register (also clears EOC flag)
        adc_buffer[i] = ADC1->DR;
        // Sample-rate probe: toggle PA1 (Nucleo A1) once per sample.
        // Direct ODR XOR — ~2 CPU cycles, negligible loop perturbation.
        GPIOA->ODR ^= GPIO_PIN_1;
    }

    // Stop ADC
    HAL_ADC_Stop(&hadc1);
}

/**
 * @brief Send all captured samples over UART in CSV format
 * Format: "index,value\r\n" for each sample
 * Starts with header, ends with END marker
 */
void send_samples_uart(void) {
    char buf[32];

    // Send header
    sprintf(buf, "--- BEGIN CAPTURE ---\r\n");
    HAL_UART_Transmit(&huart2, (uint8_t*)buf, strlen(buf), 100);

    // Send samples
    for (int i = 0; i < ADC_BUFFER_SIZE; i++) {
        sprintf(buf, "%d,%u\r\n", i, adc_buffer[i]);
        HAL_UART_Transmit(&huart2, (uint8_t*)buf, strlen(buf), 100);
    }

    // Send footer
    sprintf(buf, "--- END CAPTURE ---\r\n");
    HAL_UART_Transmit(&huart2, (uint8_t*)buf, strlen(buf), 100);
}

/**
 * @brief One-pass echo analysis: DC mean, threshold-based echo start,
 *        envelope peak, and zero-crossing interpolated sub-sample ToF.
 *
 * Layer 1 (peak detection): scan post-blanking window for first threshold
 * cross and absolute maximum deviation from DC.
 *
 * Layer 2 (ZC interpolation): walk outward from peak, find up to
 * ZC_HALF_COUNT zero crossings on each side, linearly interpolate each
 * between bracketing samples, average. Frac formula: -y0 / (y1 - y0).
 * Skips first BLANKING_SAMPLES to ignore TX feedthrough + RX ringup.
 */
echo_analysis_t analyze_echo(uint16_t *buf, int n) {
    echo_analysis_t r = { 0 };
    r.echo_start_idx = -1;

    // ---- DC mean over whole buffer (echo is ~symmetric, low bias) ----
    uint32_t sum = 0;
    for (int i = 0; i < n; i++) sum += buf[i];
    r.dc_mean = (float)sum / (float)n;
    int dc_int = (int)(r.dc_mean + 0.5f);

    // ---- Layer 1: threshold cross + envelope peak ----
    int max_dev = 0;
    int max_idx = BLANKING_SAMPLES;
    for (int i = BLANKING_SAMPLES; i < n; i++) {
        int dev = (int)buf[i] - dc_int;
        int abs_dev = dev < 0 ? -dev : dev;
        if (r.echo_start_idx < 0 && abs_dev > ECHO_THRESHOLD) {
            r.echo_start_idx = i;
        }
        if (abs_dev > max_dev) {
            max_dev = abs_dev;
            max_idx = i;
        }
    }
    r.peak_idx = max_idx;
    r.peak_amplitude = max_dev;

    // ---- Layer 2: zero-crossing interpolation around the peak ----
    // Walk LEFT from peak: collect up to ZC_HALF_COUNT crossings.
    float zc_sum = 0.0f;
    int   zc_count = 0;
    int   side_found = 0;
    for (int i = max_idx; i > 0 && side_found < ZC_HALF_COUNT; i--) {
        int y0 = (int)buf[i - 1] - dc_int;
        int y1 = (int)buf[i]     - dc_int;
        if ((y0 < 0 && y1 >= 0) || (y0 >= 0 && y1 < 0)) {
            int dy = y1 - y0;
            if (dy != 0) {
                float frac = (float)(-y0) / (float)dy;
                zc_sum += (float)(i - 1) + frac;
                zc_count++;
                side_found++;
            }
        }
    }
    // Walk RIGHT from peak: collect up to ZC_HALF_COUNT more.
    side_found = 0;
    for (int i = max_idx; i < n - 1 && side_found < ZC_HALF_COUNT; i++) {
        int y0 = (int)buf[i]     - dc_int;
        int y1 = (int)buf[i + 1] - dc_int;
        if ((y0 < 0 && y1 >= 0) || (y0 >= 0 && y1 < 0)) {
            int dy = y1 - y0;
            if (dy != 0) {
                float frac = (float)(-y0) / (float)dy;
                zc_sum += (float)i + frac;
                zc_count++;
                side_found++;
            }
        }
    }
    r.zc_count   = zc_count;
    r.zc_avg_idx = (zc_count > 0) ? (zc_sum / (float)zc_count) : 0.0f;

    return r;
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */

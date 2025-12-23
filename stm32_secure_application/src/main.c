/**
 * ============================================================================
 * STM32F103 - APPLICATION HAL COMPLÈTE - SECURE BOOT COMPATIBLE
 * Support JSON + Commandes TEXTE
 * ============================================================================
 */

#include "stm32f1xx_hal.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>

/* ============================================================================
   HANDLES & BUFFERS
   ============================================================================ */
UART_HandleTypeDef huart2;
ADC_HandleTypeDef hadc1;
TIM_HandleTypeDef htim2;
DMA_HandleTypeDef hdma_usart2_rx;
DMA_HandleTypeDef hdma_usart2_tx;
DMA_HandleTypeDef hdma_adc1;

#define UART_RX_BUFFER_SIZE 512
#define CMD_BUFFER_SIZE 512
#define ADC_BUFFER_SIZE 16

uint8_t uart_rx_buffer[UART_RX_BUFFER_SIZE];
uint8_t uart_tx_buffer[UART_RX_BUFFER_SIZE];
uint16_t adc_buffer[ADC_BUFFER_SIZE];
char cmd_buffer[CMD_BUFFER_SIZE];

volatile uint16_t rx_old_pos = 0;
volatile uint16_t cmd_index = 0;

/* ============================================================================
   DEVICE STATE
   ============================================================================ */
typedef struct {
    float temperature;
    float voltage;
    uint16_t adc_raw;
    uint8_t pwm_duty;
    uint8_t led_state;
    uint32_t uptime;
    uint32_t rx_count;
} DeviceState_t;

volatile DeviceState_t device = {.temperature = 25.0f};

/* ============================================================================
   PROTOTYPES
   ============================================================================ */
void System_FullReinit(void);
void SystemClock_Config(void);
void GPIO_Init(void);
void DMA_Init(void);
void USART2_Init(void);
void ADC1_Init(void);
void TIM2_PWM_Init(void);

void checkDMABuffer(void);
void processChar(uint8_t c);
void processCommand(char *cmd);
void sendResponse(const char *msg);
void updateADC(void);
void setPWM(uint8_t duty);
static void trim(char *s);

// JSON helpers
int isJsonCommand(const char *str);
int extractJsonString(const char *json, const char *key, char *out, int maxLen);
int extractJsonInt(const char *json, const char *key, int *out);

/* ============================================================================
   MAIN
   ============================================================================ */
int main(void) {
    // 🔥 CRITIQUE: Reset système AVANT HAL
    System_FullReinit();
    
    // Init HAL
    HAL_Init();
    SystemClock_Config();
    GPIO_Init();
    DMA_Init();
    USART2_Init();
    ADC1_Init();
    TIM2_PWM_Init();
    
    // 3 blinks = app démarre
    for(int i = 0; i < 3; i++) {
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
        HAL_Delay(100);
        HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
        HAL_Delay(100);
    }
    
    // Message de bienvenue
    sendResponse("READY\r\n");
    
    // Démarre DMA
    HAL_UART_Receive_DMA(&huart2, uart_rx_buffer, UART_RX_BUFFER_SIZE);
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, ADC_BUFFER_SIZE);
    
    uint32_t last_heartbeat = HAL_GetTick();
    uint32_t last_adc = HAL_GetTick();
    
    while(1) {
        checkDMABuffer();
        
        // Update ADC toutes les 100ms
        if (HAL_GetTick() - last_adc > 100) {
            updateADC();
            last_adc = HAL_GetTick();
        }
        
        // Heartbeat toutes les 5s
        if (HAL_GetTick() - last_heartbeat > 5000) {
            char msg[64];
            snprintf(msg, sizeof(msg), "UP:%lus V:%.2f PWM:%u\r\n",
                    device.uptime, device.voltage, device.pwm_duty);
            sendResponse(msg);
            last_heartbeat = HAL_GetTick();
        }
        
        device.uptime = HAL_GetTick() / 1000;
        HAL_Delay(10);
    }
}

/* ============================================================================
   SYSTEM REINIT
   ============================================================================ */
void System_FullReinit(void) {
    __disable_irq();
    
    SysTick->CTRL = 0;
    SysTick->LOAD = 0;
    SysTick->VAL = 0;
    
    for (uint8_t i = 0; i < 8; i++) {
        NVIC->ICER[i] = 0xFFFFFFFF;
        NVIC->ICPR[i] = 0xFFFFFFFF;
    }
    
    RCC->CR = 0x00000083;
    RCC->CFGR = 0x00000000;
    RCC->CIR = 0x00000000;
    RCC->AHBENR = 0x00000014;
    
    RCC->APB2RSTR = 0xFFFFFFFF;
    RCC->APB2RSTR = 0x00000000;
    RCC->APB1RSTR = 0xFFFFFFFF;
    RCC->APB1RSTR = 0x00000000;
    
    RCC->APB2ENR = 0x00000000;
    RCC->APB1ENR = 0x00000000;
    
    NVIC_SetPriorityGrouping(0);
    
    __DSB();
    __ISB();
    __enable_irq();
}

/* ============================================================================
   UART DMA PARSING
   ============================================================================ */
void checkDMABuffer(void) {
    uint16_t pos = UART_RX_BUFFER_SIZE - __HAL_DMA_GET_COUNTER(huart2.hdmarx);
    
    if (pos != rx_old_pos) {
        if (pos < rx_old_pos) {
            for (uint16_t i = rx_old_pos; i < UART_RX_BUFFER_SIZE; i++)
                processChar(uart_rx_buffer[i]);
            rx_old_pos = 0;
        }
        for (uint16_t i = rx_old_pos; i < pos; i++)
            processChar(uart_rx_buffer[i]);
        rx_old_pos = pos;
    }
}

void processChar(uint8_t c) {
    device.rx_count++;
    
    if (c == '\n' || c == '\r') {
        if (cmd_index > 0) {
            cmd_buffer[cmd_index] = 0;
            trim(cmd_buffer);
            if (strlen(cmd_buffer) > 0)
                processCommand(cmd_buffer);
            cmd_index = 0;
        }
    } else if (cmd_index < CMD_BUFFER_SIZE - 1) {
        cmd_buffer[cmd_index++] = c;
    } else {
        cmd_index = 0;
    }
}

/* ============================================================================
   JSON PARSER SIMPLE
   ============================================================================ */

// Vérifie si c'est du JSON (commence par '{' et contient "command")
int isJsonCommand(const char *str) {
    if (str[0] != '{') return 0;
    if (strstr(str, "\"command\"") == NULL) return 0;
    return 1;
}

// Extrait une valeur string entre guillemets
int extractJsonString(const char *json, const char *key, char *out, int maxLen) {
    char search[64];
    snprintf(search, sizeof(search), "\"%s\":\"", key);
    
    const char *start = strstr(json, search);
    if (!start) return 0;
    
    start += strlen(search);
    const char *end = strchr(start, '"');
    if (!end) return 0;
    
    int len = end - start;
    if (len >= maxLen) len = maxLen - 1;
    
    strncpy(out, start, len);
    out[len] = 0;
    return 1;
}

// Extrait une valeur numérique depuis params.key
int extractJsonInt(const char *json, const char *key, int *out) {
    // Cherche "params":{
    const char *params = strstr(json, "\"params\"");
    if (!params) return 0;
    
    // Cherche le début de l'objet params
    const char *obj_start = strchr(params, '{');
    if (!obj_start) return 0;
    
    // Cherche la clé dans params
    char search[64];
    snprintf(search, sizeof(search), "\"%s\":", key);
    
    const char *key_pos = strstr(obj_start, search);
    if (!key_pos) return 0;
    
    const char *val_start = key_pos + strlen(search);
    
    // Skip whitespace
    while (*val_start == ' ' || *val_start == '\t') val_start++;
    
    // Parse le nombre
    if (!isdigit(*val_start) && *val_start != '-') return 0;
    
    *out = atoi(val_start);
    return 1;
}

/* ============================================================================
   COMMANDS - JSON + TEXTE
   ============================================================================ */
void processCommand(char *cmd) {
    char resp[256];
    
    // ============================================================================
    // 🔥 DÉTECTION ET TRAITEMENT JSON
    // ============================================================================
    if (isJsonCommand(cmd)) {
        char command[32] = {0};
        int state = 0;
        int duty = 0;
        
        // Extrait le nom de la commande
        if (!extractJsonString(cmd, "command", command, sizeof(command))) {
            sendResponse("{\"status\":\"error\",\"message\":\"Invalid JSON\"}\r\n");
            return;
        }
        
        // 📌 COMMANDE JSON: SET_LED
        if (!strcmp(command, "SET_LED")) {
            if (extractJsonInt(cmd, "state", &state)) {
                if (state == 1) {
                    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
                    device.led_state = 1;
                    sendResponse("{\"status\":\"ok\",\"message\":\"LED ON\"}\r\n");
                } else {
                    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
                    device.led_state = 0;
                    sendResponse("{\"status\":\"ok\",\"message\":\"LED OFF\"}\r\n");
                }
            } else {
                sendResponse("{\"status\":\"error\",\"message\":\"Missing state\"}\r\n");
            }
            return;
        }
        
        // 📌 COMMANDE JSON: SET_PWM
        else if (!strcmp(command, "SET_PWM")) {
            if (extractJsonInt(cmd, "duty", &duty)) {
                if (duty >= 0 && duty <= 100) {
                    setPWM(duty);
                    device.pwm_duty = duty;
                    snprintf(resp, sizeof(resp), 
                            "{\"status\":\"ok\",\"message\":\"PWM=%d%%\"}\r\n", duty);
                    sendResponse(resp);
                } else {
                    sendResponse("{\"status\":\"error\",\"message\":\"PWM 0-100\"}\r\n");
                }
            } else {
                sendResponse("{\"status\":\"error\",\"message\":\"Missing duty\"}\r\n");
            }
            return;
        }
        
        // 📌 COMMANDE JSON: GET_TEMP
        else if (!strcmp(command, "GET_TEMP")) {
            snprintf(resp, sizeof(resp), 
                    "{\"status\":\"ok\",\"temperature\":%.1f}\r\n", 
                    device.temperature);
            sendResponse(resp);
            return;
        }
        
        // 📌 COMMANDE JSON: GET_VOLTAGE
        else if (!strcmp(command, "GET_VOLTAGE")) {
            snprintf(resp, sizeof(resp), 
                    "{\"status\":\"ok\",\"voltage\":%.2f,\"adc_raw\":%u}\r\n", 
                    device.voltage, device.adc_raw);
            sendResponse(resp);
            return;
        }
        
        // 📌 COMMANDE JSON: STATUS
        else if (!strcmp(command, "STATUS")) {
            snprintf(resp, sizeof(resp),
                    "{\"status\":\"ok\",\"led\":%s,\"uptime\":%lu,\"voltage\":%.2f,\"pwm\":%u}\r\n",
                    device.led_state ? "true" : "false",
                    device.uptime, device.voltage, device.pwm_duty);
            sendResponse(resp);
            return;
        }
        
        // 📌 COMMANDE JSON: RESET
        else if (!strcmp(command, "RESET")) {
            sendResponse("{\"status\":\"ok\",\"message\":\"Resetting...\"}\r\n");
            HAL_Delay(100);
            NVIC_SystemReset();
            return;
        }
        
        // Commande JSON inconnue
        else {
            snprintf(resp, sizeof(resp), 
                    "{\"status\":\"error\",\"message\":\"Unknown: %s\"}\r\n", 
                    command);
            sendResponse(resp);
            return;
        }
    }
    
    // ============================================================================
    // 📝 COMMANDES TEXTE CLASSIQUES
    // ============================================================================
    
    if (!strcmp(cmd, "PING")) {
        sendResponse("PONG\r\n");
    }
    else if (!strcmp(cmd, "STATUS")) {
        snprintf(resp, sizeof(resp),
            "STATUS: OK | LED:%s | UP:%lus | V:%.2fV | PWM:%u%%\r\n",
            device.led_state ? "ON" : "OFF",
            device.uptime, device.voltage, device.pwm_duty);
        sendResponse(resp);
    }
    else if (!strcmp(cmd, "TEMP")) {
        snprintf(resp, sizeof(resp), "TEMP: %.1f°C\r\n", device.temperature);
        sendResponse(resp);
    }
    else if (!strcmp(cmd, "VOLTAGE")) {
        snprintf(resp, sizeof(resp), "VOLTAGE: %.2fV (ADC:%u)\r\n",
                device.voltage, device.adc_raw);
        sendResponse(resp);
    }
    else if (!strncmp(cmd, "LED=", 4)) {
        int val = atoi(cmd + 4);
        if (val == 1) {
            HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
            device.led_state = 1;
            sendResponse("OK: LED ON\r\n");
        } else {
            HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
            device.led_state = 0;
            sendResponse("OK: LED OFF\r\n");
        }
    }
    else if (!strncmp(cmd, "PWM=", 4)) {
        int val = atoi(cmd + 4);
        if (val >= 0 && val <= 100) {
            setPWM(val);
            device.pwm_duty = val;
            snprintf(resp, sizeof(resp), "OK: PWM=%u%%\r\n", val);
            sendResponse(resp);
        } else {
            sendResponse("ERROR: PWM 0-100\r\n");
        }
    }
    else if (!strcmp(cmd, "RESET")) {
        sendResponse("RESETTING...\r\n");
        HAL_Delay(100);
        NVIC_SystemReset();
    }
    else {
        snprintf(resp, sizeof(resp), "ERROR: Unknown '%s'\r\n", cmd);
        sendResponse(resp);
    }
}

/* ============================================================================
   UART TX
   ============================================================================ */
void sendResponse(const char *msg) {
    uint16_t len = strlen(msg);
    if (len > UART_RX_BUFFER_SIZE) len = UART_RX_BUFFER_SIZE;
    memcpy(uart_tx_buffer, msg, len);
    HAL_UART_Transmit_DMA(&huart2, uart_tx_buffer, len);
    while (huart2.gState != HAL_UART_STATE_READY);
}

/* ============================================================================
   ADC / PWM
   ============================================================================ */
void updateADC(void) {
    uint32_t sum = 0;
    for (int i = 0; i < ADC_BUFFER_SIZE; i++)
        sum += adc_buffer[i];
    device.adc_raw = sum / ADC_BUFFER_SIZE;
    device.voltage = (device.adc_raw * 3.3f) / 4095.0f;
}

void setPWM(uint8_t duty) {
    if (duty > 100) duty = 100;
    uint32_t pulse = (duty * 999) / 100;
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, pulse);
}

/* ============================================================================
   INIT
   ============================================================================ */
void DMA_Init(void) {
    __HAL_RCC_DMA1_CLK_ENABLE();
    
    hdma_usart2_rx.Instance = DMA1_Channel6;
    hdma_usart2_rx.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_usart2_rx.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_usart2_rx.Init.MemInc = DMA_MINC_ENABLE;
    hdma_usart2_rx.Init.PeriphDataAlignment = DMA_PDATAALIGN_BYTE;
    hdma_usart2_rx.Init.MemDataAlignment = DMA_MDATAALIGN_BYTE;
    hdma_usart2_rx.Init.Mode = DMA_CIRCULAR;
    hdma_usart2_rx.Init.Priority = DMA_PRIORITY_HIGH;
    HAL_DMA_Init(&hdma_usart2_rx);
    
    hdma_usart2_tx.Instance = DMA1_Channel7;
    hdma_usart2_tx.Init.Direction = DMA_MEMORY_TO_PERIPH;
    hdma_usart2_tx.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_usart2_tx.Init.MemInc = DMA_MINC_ENABLE;
    hdma_usart2_tx.Init.PeriphDataAlignment = DMA_PDATAALIGN_BYTE;
    hdma_usart2_tx.Init.MemDataAlignment = DMA_MDATAALIGN_BYTE;
    hdma_usart2_tx.Init.Mode = DMA_NORMAL;
    hdma_usart2_tx.Init.Priority = DMA_PRIORITY_HIGH;
    HAL_DMA_Init(&hdma_usart2_tx);
    
    hdma_adc1.Instance = DMA1_Channel1;
    hdma_adc1.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_adc1.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_adc1.Init.MemInc = DMA_MINC_ENABLE;
    hdma_adc1.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
    hdma_adc1.Init.MemDataAlignment = DMA_MDATAALIGN_HALFWORD;
    hdma_adc1.Init.Mode = DMA_CIRCULAR;
    hdma_adc1.Init.Priority = DMA_PRIORITY_MEDIUM;
    HAL_DMA_Init(&hdma_adc1);
    
    HAL_NVIC_SetPriority(DMA1_Channel7_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(DMA1_Channel7_IRQn);
}

void USART2_Init(void) {
    __HAL_RCC_USART2_CLK_ENABLE();
    
    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200;
    huart2.Init.WordLength = UART_WORDLENGTH_8B;
    huart2.Init.StopBits = UART_STOPBITS_1;
    huart2.Init.Parity = UART_PARITY_NONE;
    huart2.Init.Mode = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart2);
    
    __HAL_LINKDMA(&huart2, hdmarx, hdma_usart2_rx);
    __HAL_LINKDMA(&huart2, hdmatx, hdma_usart2_tx);
    
    HAL_NVIC_SetPriority(USART2_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(USART2_IRQn);
}

void ADC1_Init(void) {
    __HAL_RCC_ADC1_CLK_ENABLE();
    
    hadc1.Instance = ADC1;
    hadc1.Init.ScanConvMode = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode = ENABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = 1;
    HAL_ADC_Init(&hadc1);
    
    __HAL_LINKDMA(&hadc1, DMA_Handle, hdma_adc1);
    
    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Channel = ADC_CHANNEL_0;
    sConfig.Rank = ADC_REGULAR_RANK_1;
    sConfig.SamplingTime = ADC_SAMPLETIME_55CYCLES_5;
    HAL_ADC_ConfigChannel(&hadc1, &sConfig);
}

void TIM2_PWM_Init(void) {
    __HAL_RCC_TIM2_CLK_ENABLE();
    
    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 7;
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = 999;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_PWM_Init(&htim2);
    
    TIM_OC_InitTypeDef sConfig = {0};
    sConfig.OCMode = TIM_OCMODE_PWM1;
    sConfig.Pulse = 0;
    sConfig.OCPolarity = TIM_OCPOLARITY_HIGH;
    sConfig.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim2, &sConfig, TIM_CHANNEL_2);
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2);
}

void GPIO_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();
    
    GPIO_InitTypeDef g = {0};
    
    // LED PC13
    g.Pin = GPIO_PIN_13;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &g);
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
    
    // UART2 TX (PA2)
    g.Pin = GPIO_PIN_2;
    g.Mode = GPIO_MODE_AF_PP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);
    
    // UART2 RX (PA3)
    g.Pin = GPIO_PIN_3;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &g);
    
    // PWM TIM2_CH2 (PA1)
    g.Pin = GPIO_PIN_1;
    g.Mode = GPIO_MODE_AF_PP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);
    
    // ADC (PA0)
    g.Pin = GPIO_PIN_0;
    g.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &g);
}

void SystemClock_Config(void) {
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    RCC_PeriphCLKInitTypeDef pclk = {0};
    
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    osc.HSIState = RCC_HSI_ON;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.PLL.PLLState = RCC_PLL_NONE;
    HAL_RCC_OscConfig(&osc);
    
    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                    RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV1;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_0);
    
    pclk.PeriphClockSelection = RCC_PERIPHCLK_ADC;
    pclk.AdcClockSelection = RCC_ADCPCLK2_DIV2;
    HAL_RCCEx_PeriphCLKConfig(&pclk);
}

/* ============================================================================
   IRQ HANDLERS
   ============================================================================ */
void SysTick_Handler(void) {
    HAL_IncTick();
}

void USART2_IRQHandler(void) {
    HAL_UART_IRQHandler(&huart2);
}

void DMA1_Channel7_IRQHandler(void) {
    HAL_DMA_IRQHandler(&hdma_usart2_tx);
}

/* ============================================================================
   UTILS
   ============================================================================ */
static void trim(char *s) {
    while (*s == ' ') memmove(s, s + 1, strlen(s));
    char *e = s + strlen(s) - 1;
    while (e > s && (*e == '\n' || *e == '\r' || *e == ' ')) *e-- = 0;
}
/**
 * ============================================================================
 * SECURE BOOTLOADER - STM32F103 - VERSION FINALE STABLE
 * ============================================================================
 */

#include "stm32f1xx_hal.h"
#include <string.h>
#include "crypto_light.h"

#define APPLICATION_ADDRESS  0x08002000
#define APPLICATION_MAX_SIZE 0xC000
#define METADATA_ADDR        0x0800E000
#define LED_PORT GPIOC
#define LED_PIN  GPIO_PIN_13

typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t size;
    uint32_t crc32;
    uint8_t  sha256[32];
    uint32_t timestamp;
    uint8_t  reserved[32];
} __attribute__((packed)) FirmwareMetadata_t;

void SystemClock_Config(void);
void GPIO_Init(void);
void LED_Blink(uint32_t count, uint32_t on_ms, uint32_t off_ms);
void LED_Error_Loop(uint32_t pattern);
uint8_t Verify_Firmware(void);
void Jump_To_Application(void) __attribute__((noreturn));
uint32_t Calculate_CRC32(const uint8_t *data, uint32_t length);

int main(void) {
    HAL_Init();
    SystemClock_Config();
    GPIO_Init();
    
    HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
    HAL_Delay(100);
    
    LED_Blink(2, 100, 100);
    HAL_Delay(500);
    
    if (Verify_Firmware()) {
        LED_Blink(3, 200, 200);
        HAL_Delay(200);
        Jump_To_Application();
    }
    
    HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
    while(1) __WFI();
}

uint8_t Verify_Firmware(void) {
    FirmwareMetadata_t *metadata = (FirmwareMetadata_t*)METADATA_ADDR;
    
    if (metadata->magic != 0xDEADBEEF) {
        LED_Error_Loop(1);
        return 0;
    }
    
    if (metadata->size == 0 || metadata->size > APPLICATION_MAX_SIZE) {
        LED_Error_Loop(2);
        return 0;
    }
    
    uint32_t stack_pointer = *(__IO uint32_t*)APPLICATION_ADDRESS;
    if ((stack_pointer & 0x2FFE0000) != 0x20000000) {
        LED_Error_Loop(5);
        return 0;
    }
    
    uint8_t *firmware = (uint8_t*)APPLICATION_ADDRESS;
    uint32_t calculated_crc = Calculate_CRC32(firmware, metadata->size);
    
    if (calculated_crc != metadata->crc32) {
        LED_Error_Loop(2);
        return 0;
    }
    
    uint8_t calculated_hash[32];
    sha256_hash(firmware, metadata->size, calculated_hash);
    
    if (memcmp(calculated_hash, metadata->sha256, 32) != 0) {
        LED_Error_Loop(3);
        return 0;
    }
    
    return 1;
}

void Jump_To_Application(void) {
    __disable_irq();
    
    SysTick->CTRL = 0;
    SysTick->LOAD = 0;
    SysTick->VAL = 0;
    
    for (uint8_t i = 0; i < 8; i++) {
        NVIC->ICER[i] = 0xFFFFFFFF;
        NVIC->ICPR[i] = 0xFFFFFFFF;
    }
    
    // NE TOUCHE PAS RCC - l'application le fera
    
    SCB->VTOR = APPLICATION_ADDRESS;
    __DSB();
    __ISB();
    
    uint32_t app_stack = *(__IO uint32_t*)APPLICATION_ADDRESS;
    uint32_t app_reset = *(__IO uint32_t*)(APPLICATION_ADDRESS + 4);
    
    __set_MSP(app_stack);
    __DSB();
    __ISB();
    
    void (*app_reset_handler)(void) = (void (*)(void))app_reset;
    app_reset_handler();
    
    while(1);
}

uint32_t Calculate_CRC32(const uint8_t *data, uint32_t length) {
    uint32_t crc = 0xFFFFFFFF;
    for (uint32_t i = 0; i < length; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            crc = (crc & 1) ? ((crc >> 1) ^ 0xEDB88320) : (crc >> 1);
        }
    }
    return ~crc;
}

void LED_Blink(uint32_t count, uint32_t on_ms, uint32_t off_ms) {
    for (uint32_t i = 0; i < count; i++) {
        HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
        HAL_Delay(on_ms);
        HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
        if (i < count - 1) HAL_Delay(off_ms);
    }
}

void LED_Error_Loop(uint32_t pattern) {
    while(1) {
        if (pattern == 1) {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
            HAL_Delay(2000);
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
            HAL_Delay(500);
        } else if (pattern == 2) {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
            HAL_Delay(1000);
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
            HAL_Delay(200);
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
            HAL_Delay(300);
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
            HAL_Delay(500);
        } else {
            LED_Blink(pattern, 200, 200);
            HAL_Delay(1000);
        }
    }
}

void GPIO_Init(void) {
    __HAL_RCC_GPIOC_CLK_ENABLE();
    
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = LED_PIN;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &GPIO_InitStruct);
    
    HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
}

void SystemClock_Config(void) {
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
    
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
    HAL_RCC_OscConfig(&RCC_OscInitStruct);
    
    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                  RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0);
}

void SysTick_Handler(void) {
    HAL_IncTick();
}
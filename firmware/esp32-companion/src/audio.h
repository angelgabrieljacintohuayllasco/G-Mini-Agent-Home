// Microfono INMP441 (I2S0, RX) y amplificador MAX98357A (I2S1, TX).
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace audio {

bool begin();
bool ready();

// ----------------------------------------------------------- microfono
// Lee muestras mono PCM16 a 16 kHz. Devuelve cuantas leyo (0 si vencio el plazo).
size_t micRead(int16_t* out, size_t maxSamples, uint32_t timeoutMs);
// Descarta lo acumulado en el DMA (llamar antes de empezar a grabar).
void micFlush();

// Bufer de grabacion reservado al arrancar (PSRAM si existe).
int16_t* recordBuffer();
size_t recordCapacity();  // en muestras

// ----------------------------------------------------------- parlante
void setVolume(uint8_t volume);  // 0..100
bool speakerBegin(uint32_t sampleRate, uint16_t channels);
// Muestras PCM16 entrelazadas segun los canales indicados en speakerBegin.
void speakerWrite(const int16_t* samples, size_t count);
void speakerEnd();

// Tonos de aviso (no bloquean la cara; si bloquean el bucle principal unos ms).
void chime(bool rising);
void errorTone();

// Nivel 0..1 de un bloque (RMS con curva perceptual), para animar boca y LEDs.
float levelOf(const int16_t* samples, size_t count, uint16_t stride = 1);

}  // namespace audio

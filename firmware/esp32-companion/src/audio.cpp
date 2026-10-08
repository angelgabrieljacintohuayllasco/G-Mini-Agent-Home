#include "audio.h"

#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

#include "config.h"

namespace audio {

namespace {

const i2s_port_t kMicPort = I2S_NUM_0;
const i2s_port_t kSpkPort = I2S_NUM_1;

bool gReady = false;
int16_t* gRecord = nullptr;
size_t gRecordCap = 0;
int32_t gGainQ8 = 256 * 36 / 100;  // volumen 60 % con curva cuadratica
uint32_t gSpkRate = GMINI_SAMPLE_RATE;
uint16_t gSpkChannels = 1;
int32_t gDc = 0;
// Canal del INMP441: -1 sin decidir, 0 izquierdo, 1 derecho. Se elige el que tiene senal.
int8_t gMicSlot = -1;
int32_t gRaw[256];
int16_t gFrames[512];

bool installMic() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
  cfg.sample_rate = GMINI_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;
  if (i2s_driver_install(kMicPort, &cfg, 0, nullptr) != ESP_OK) return false;
  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = PIN_MIC_SCK;
  pins.ws_io_num = PIN_MIC_WS;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = PIN_MIC_SD;
  return i2s_set_pin(kMicPort, &pins) == ESP_OK;
}

bool installSpeaker() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = GMINI_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 512;
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;  // silencio si el DMA se queda sin datos
  if (i2s_driver_install(kSpkPort, &cfg, 0, nullptr) != ESP_OK) return false;
  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = PIN_AMP_BCLK;
  pins.ws_io_num = PIN_AMP_LRC;
  pins.data_out_num = PIN_AMP_DIN;
  pins.data_in_num = I2S_PIN_NO_CHANGE;
  if (i2s_set_pin(kSpkPort, &pins) != ESP_OK) return false;
  i2s_zero_dma_buffer(kSpkPort);
  return true;
}

inline int16_t clamp16(int32_t v) { return v > 32767 ? 32767 : (v < -32768 ? -32768 : (int16_t)v); }

void writeFrames(const int16_t* frames, size_t frameCount) {
  size_t written = 0;
  i2s_write(kSpkPort, frames, frameCount * 2 * sizeof(int16_t), &written, portMAX_DELAY);
}

void tone(float freq, uint16_t ms, float amp) {
  speakerBegin(GMINI_SAMPLE_RATE, 1);
  const size_t total = (size_t)GMINI_SAMPLE_RATE * ms / 1000;
  const size_t fade = GMINI_SAMPLE_RATE / 200;  // 5 ms de rampa evita clics
  int16_t block[256];
  for (size_t i = 0; i < total;) {
    size_t n = total - i < 256 ? total - i : 256;
    for (size_t k = 0; k < n; ++k) {
      size_t idx = i + k;
      float env = 1.0f;
      if (idx < fade) env = (float)idx / fade;
      if (total - idx < fade) env = (float)(total - idx) / fade;
      block[k] = (int16_t)(amp * env * 32767.0f * sinf(2.0f * PI * freq * idx / GMINI_SAMPLE_RATE));
    }
    speakerWrite(block, n);
    i += n;
  }
}

}  // namespace

bool begin() {
  gRecordCap = (size_t)GMINI_SAMPLE_RATE * GMINI_MAX_RECORD_SECONDS;
#if defined(BOARD_HAS_PSRAM)
  if (psramFound()) gRecord = (int16_t*)ps_malloc(gRecordCap * sizeof(int16_t));
#endif
  if (gRecord == nullptr) gRecord = (int16_t*)malloc(gRecordCap * sizeof(int16_t));
  if (gRecord == nullptr) {
    // Sin memoria suficiente: grabaciones mas cortas antes que no grabar.
    gRecordCap = GMINI_SAMPLE_RATE * 2;
    gRecord = (int16_t*)malloc(gRecordCap * sizeof(int16_t));
    if (gRecord == nullptr) gRecordCap = 0;
  }
  const bool mic = installMic();
  const bool spk = installSpeaker();
  gReady = mic && spk && gRecord != nullptr;
  log_i("audio: mic=%d parlante=%d bufer=%u muestras", mic, spk, (unsigned)gRecordCap);
  return gReady;
}

bool ready() { return gReady; }

int16_t* recordBuffer() { return gRecord; }
size_t recordCapacity() { return gRecordCap; }

void micFlush() {
  i2s_zero_dma_buffer(kMicPort);
  size_t got = 0;
  // Vacia lo que el DMA tenga guardado de antes.
  while (i2s_read(kMicPort, gRaw, sizeof(gRaw), &got, 0) == ESP_OK && got > 0) {
  }
  gDc = 0;
}

size_t micRead(int16_t* out, size_t maxSamples, uint32_t timeoutMs) {
  if (!gReady || maxSamples == 0) return 0;
  size_t want = maxSamples * 2;  // dos ranuras (izq/der) por muestra
  if (want > sizeof(gRaw) / sizeof(gRaw[0])) want = sizeof(gRaw) / sizeof(gRaw[0]);
  size_t got = 0;
  if (i2s_read(kMicPort, gRaw, want * sizeof(int32_t), &got, pdMS_TO_TICKS(timeoutMs)) != ESP_OK) return 0;
  const size_t frames = got / (2 * sizeof(int32_t));
  if (frames == 0) return 0;

  if (gMicSlot < 0) {
    // Elige la ranura con energia: el pin L/R del INMP441 decide en cual transmite.
    int64_t e0 = 0, e1 = 0;
    for (size_t i = 0; i < frames; ++i) {
      int32_t a = gRaw[2 * i] >> 16, b = gRaw[2 * i + 1] >> 16;
      e0 += (int64_t)a * a;
      e1 += (int64_t)b * b;
    }
    if (e0 > 4 * e1 + 1000) gMicSlot = 0;
    if (e1 > 4 * e0 + 1000) gMicSlot = 1;
  }
  const int slot = gMicSlot < 0 ? 0 : gMicSlot;
  for (size_t i = 0; i < frames; ++i) {
    int32_t v = gRaw[2 * i + slot] >> GMINI_MIC_SHIFT;
    // Filtro paso alto de un polo: quita la componente continua del microfono.
    gDc += (v * 256 - gDc) >> 9;
    out[i] = clamp16(v - (gDc >> 8));
  }
  return frames;
}

void setVolume(uint8_t volume) {
  if (volume > 100) volume = 100;
  gGainQ8 = (int32_t)(256L * volume * volume / 10000L);
}

bool speakerBegin(uint32_t sampleRate, uint16_t channels) {
  if (!gReady) return false;
  if (sampleRate < 8000 || sampleRate > 48000 || channels < 1 || channels > 2) return false;
  if (sampleRate != gSpkRate) {
    i2s_set_clk(kSpkPort, sampleRate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_STEREO);
    gSpkRate = sampleRate;
  }
  gSpkChannels = channels;
  return true;
}

void speakerWrite(const int16_t* samples, size_t count) {
  if (!gReady) return;
  const size_t maxFrames = sizeof(gFrames) / sizeof(gFrames[0]) / 2;
  const size_t frames = count / gSpkChannels;
  for (size_t done = 0; done < frames;) {
    size_t n = frames - done < maxFrames ? frames - done : maxFrames;
    for (size_t i = 0; i < n; ++i) {
      const size_t src = (done + i) * gSpkChannels;
      const int16_t l = clamp16((samples[src] * gGainQ8) >> 8);
      const int16_t r = gSpkChannels == 2 ? clamp16((samples[src + 1] * gGainQ8) >> 8) : l;
      gFrames[2 * i] = l;
      gFrames[2 * i + 1] = r;
    }
    writeFrames(gFrames, n);
    done += n;
  }
}

void speakerEnd() {
  if (!gReady) return;
  // Unos ms de silencio antes de limpiar el DMA evitan el "pop" del amplificador.
  memset(gFrames, 0, sizeof(gFrames));
  writeFrames(gFrames, sizeof(gFrames) / sizeof(gFrames[0]) / 2);
  i2s_zero_dma_buffer(kSpkPort);
}

void chime(bool rising) {
  if (!gReady) return;
  tone(rising ? 880.0f : 1320.0f, 70, 0.35f);
  tone(rising ? 1320.0f : 880.0f, 90, 0.35f);
  speakerEnd();
}

void errorTone() {
  if (!gReady) return;
  tone(330.0f, 120, 0.4f);
  tone(247.0f, 180, 0.4f);
  speakerEnd();
}

float levelOf(const int16_t* samples, size_t count, uint16_t stride) {
  if (count == 0 || stride == 0) return 0.0f;
  int64_t acc = 0;
  size_t n = 0;
  for (size_t i = 0; i < count; i += stride, ++n) acc += (int32_t)samples[i] * samples[i];
  const float rms = sqrtf((float)acc / (float)n) / 32768.0f;
  // ~ -50 dBFS -> 0, ~ -10 dBFS -> 1
  float db = 20.0f * log10f(rms + 1e-6f);
  float level = (db + 50.0f) / 40.0f;
  return level < 0.0f ? 0.0f : (level > 1.0f ? 1.0f : level);
}

}  // namespace audio

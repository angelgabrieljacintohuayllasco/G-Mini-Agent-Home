#include "voice.h"

#include <Arduino.h>
#include <GMiniEyes.h>
#include <GMiniLink.h>
#include <string.h>

#include "api.h"
#include "audio.h"
#include "config.h"
#include "ui.h"

namespace voice {

namespace {

enum class State : uint8_t { Idle, Recording, Busy };

Settings* gSettings = nullptr;
State gState = State::Idle;
size_t gSamples = 0;
uint32_t gRecordStart = 0;
char gSessionId[64] = "";

// Palabra de activacion.
gmini::link::EnergyVad gVad(GMINI_SAMPLE_RATE);
const size_t kPrerollSamples = GMINI_SAMPLE_RATE * 3 / 10;  // 300 ms antes del inicio de la voz
int16_t gPreroll[kPrerollSamples];
size_t gPrerollPos = 0;
bool gPrerollFull = false;
bool gWakeCapturing = false;
uint32_t gWakeBlockedUntil = 0;
const size_t kWakeMaxSamples = GMINI_SAMPLE_RATE * 38 / 10;  // el servidor acepta menos de 4 s

uint32_t captionMs(const char* text) {
  const uint32_t ms = 4000 + (uint32_t)strlen(text) * 55;
  return ms > 15000 ? 15000 : ms;
}

void showError(const api::Error& e) {
  ui::setActivity(gmini::Activity::Idle);
  ui::setEmotion(gmini::Emotion::Error);
  ui::caption(api::describe(e), 5000);
  audio::errorTone();
  log_w("voz: %d %s %s", e.status, e.code, e.message);
}

void applyEmotion(const char* name) {
  gmini::Emotion emotion;
  if (name && *name && gmini::parseEmotion(name, &emotion)) ui::setEmotion(emotion);
}

// Se llama cuando empieza el audio de la respuesta: la emocion y el texto ya llegaron.
const api::TurnResult* gTurn = nullptr;
void onAudioStart(void*) {
  if (!gTurn) return;
  applyEmotion(gTurn->emotion);
  if (gTurn->reply[0]) ui::caption(gTurn->reply, 0);
}

void runTurn(const int16_t* pcm, size_t samples) {
  gState = State::Busy;
  ui::setActivity(gmini::Activity::Thinking);
  ui::setLevel(0.0f);
  static api::TurnResult result;
  api::Error err = {};
  gTurn = &result;
  api::setAudioStartHook(onAudioStart, nullptr);
  const bool ok = api::voiceTurn(pcm, samples, gSessionId, &result, &err);
  api::setAudioStartHook(nullptr, nullptr);
  gTurn = nullptr;
  if (!ok) {
    showError(err);
  } else if (!result.transcript[0]) {
    ui::setActivity(gmini::Activity::Idle);
    ui::setEmotion(gmini::Emotion::Thinking);
    ui::caption("No te escuché bien", 3500);
  } else {
    if (result.sessionId[0]) strlcpy(gSessionId, result.sessionId, sizeof(gSessionId));
    applyEmotion(result.emotion);
    ui::setActivity(gmini::Activity::Idle);
    if (result.reply[0]) ui::caption(result.reply, captionMs(result.reply));
    log_i("voz: \"%s\" -> \"%s\" (%u bytes de audio)", result.transcript, result.reply, (unsigned)result.audioBytes);
  }
  audio::micFlush();
  gState = State::Idle;
}

void startRecording() {
  gState = State::Recording;
  gSamples = 0;
  gRecordStart = millis();
  gWakeCapturing = false;
  audio::micFlush();
  ui::setEmotion(gmini::Emotion::Neutral);
  ui::setActivity(gmini::Activity::Listening);
  ui::clearCaption();
}

void finishRecording() {
  const uint32_t ms = (uint32_t)(gSamples * 1000ULL / GMINI_SAMPLE_RATE);
  ui::setLevel(0.0f);
  if (ms < GMINI_MIN_RECORD_MS) {
    gState = State::Idle;
    ui::setActivity(gmini::Activity::Idle);
    ui::caption("Mantén presionado mientras hablas", 3000);
    return;
  }
  runTurn(audio::recordBuffer(), gSamples);
}

void pumpRecording() {
  int16_t* buf = audio::recordBuffer();
  const size_t room = audio::recordCapacity() - gSamples;
  if (room == 0) {
    finishRecording();  // se llego al maximo: se envia lo grabado
    return;
  }
  const size_t n = audio::micRead(buf + gSamples, room < 128 ? room : 128, 20);
  if (n) {
    ui::setLevel(audio::levelOf(buf + gSamples, n));
    gSamples += n;
  }
}

// Graba una frase y se detiene sola tras un silencio (despues de "Oye G-Mini").
size_t recordUtterance(uint32_t maxMs) {
  int16_t* buf = audio::recordBuffer();
  size_t cap = audio::recordCapacity();
  const size_t maxSamples = (size_t)GMINI_SAMPLE_RATE * maxMs / 1000;
  if (cap > maxSamples) cap = maxSamples;
  gmini::link::EnergyVad vad(GMINI_SAMPLE_RATE);
  vad.minSpeechMs = 120;
  vad.hangoverMs = 900;
  vad.maxSpeechMs = (uint16_t)(maxMs > 60000 ? 60000 : maxMs);
  audio::micFlush();
  size_t samples = 0;
  bool heard = false;
  const uint32_t start = millis();
  while (samples < cap) {
    const size_t n = audio::micRead(buf + samples, 128, 30);
    if (!n) continue;
    ui::setLevel(audio::levelOf(buf + samples, n));
    const gmini::link::EnergyVad::Event ev = vad.feed(buf + samples, n);
    samples += n;
    if (ev == gmini::link::EnergyVad::kSpeechStart) heard = true;
    if (ev == gmini::link::EnergyVad::kSpeechEnd) break;
    if (!heard && millis() - start > 5000) return 0;  // nadie hablo
  }
  ui::setLevel(0.0f);
  return heard ? samples : 0;
}

void handleWakeSegment(size_t samples) {
  if (samples < GMINI_SAMPLE_RATE * 4 / 10) return;  // demasiado corto para una frase
  static api::WakeResult wake;
  api::Error err = {};
  gState = State::Busy;
  const bool ok = api::voiceWake(audio::recordBuffer(), samples, &wake, &err);
  gState = State::Idle;
  if (!ok) {
    // Sin servidor no tiene sentido seguir enviando audio: pausa de 30 s.
    gWakeBlockedUntil = millis() + 30000;
    log_w("wake: %s", err.code);
    return;
  }
  gWakeBlockedUntil = millis() + 1200;
  if (!wake.wake) return;
  log_i("wake: \"%s\" comando=\"%s\"", wake.transcript, wake.command);
  ui::wake();
  audio::chime(true);
  if (wake.command[0]) {
    gState = State::Busy;
    ui::setActivity(gmini::Activity::Thinking);
    static api::ChatResult chat;
    if (!api::chat(wake.command, gSessionId, &chat, &err)) {
      showError(err);
    } else {
      if (chat.sessionId[0]) strlcpy(gSessionId, chat.sessionId, sizeof(gSessionId));
      ui::caption(chat.reply, 0);
      if (chat.reply[0] && !api::speak(chat.reply, &err)) showError(err);
      ui::setActivity(gmini::Activity::Idle);
      ui::caption(chat.reply, captionMs(chat.reply));
    }
    gState = State::Idle;
  } else {
    ui::setActivity(gmini::Activity::Listening);
    const size_t n = recordUtterance(8000);
    if (n) {
      runTurn(audio::recordBuffer(), n);
    } else {
      ui::setActivity(gmini::Activity::Idle);
    }
  }
  audio::micFlush();
  gVad.reset();
}

void pumpWake() {
  int16_t block[160];  // 10 ms
  const size_t n = audio::micRead(block, 160, 15);
  if (!n) return;
  for (size_t i = 0; i < n; ++i) {
    gPreroll[gPrerollPos] = block[i];
    gPrerollPos = (gPrerollPos + 1) % kPrerollSamples;
    if (gPrerollPos == 0) gPrerollFull = true;
  }
  int16_t* buf = audio::recordBuffer();
  const size_t cap = audio::recordCapacity() < kWakeMaxSamples ? audio::recordCapacity() : kWakeMaxSamples;
  if (gWakeCapturing) {
    const size_t room = cap - gSamples;
    const size_t take = n < room ? n : room;
    memcpy(buf + gSamples, block, take * sizeof(int16_t));
    gSamples += take;
  }
  const gmini::link::EnergyVad::Event ev = gVad.feed(block, n);
  if (ev == gmini::link::EnergyVad::kSpeechStart && !gWakeCapturing &&
      (int32_t)(millis() - gWakeBlockedUntil) >= 0) {
    // Copia el pre-roll en orden cronologico para no perder el inicio de "Oye".
    gWakeCapturing = true;
    gSamples = 0;
    const size_t count = gPrerollFull ? kPrerollSamples : gPrerollPos;
    const size_t start = gPrerollFull ? gPrerollPos : 0;
    for (size_t i = 0; i < count && gSamples < cap; ++i) buf[gSamples++] = gPreroll[(start + i) % kPrerollSamples];
  }
  if (gWakeCapturing && (ev == gmini::link::EnergyVad::kSpeechEnd || gSamples >= cap)) {
    gWakeCapturing = false;
    const size_t samples = gSamples;
    gSamples = 0;
    handleWakeSegment(samples);
  }
}

}  // namespace

void begin(Settings* settings) {
  gSettings = settings;
  gVad.maxSpeechMs = 3800;
}

void loop() {
  if (!audio::ready()) return;
  if (gState == State::Recording) {
    pumpRecording();
    return;
  }
  if (gState == State::Idle && gSettings && gSettings->wakeWord && gSettings->paired()) pumpWake();
}

void talkPressed() {
  if (gState == State::Busy || !audio::ready()) return;
  if (!gSettings || !gSettings->paired()) {
    ui::caption("Primero empareja este dispositivo", 4000);
    return;
  }
  audio::chime(true);
  startRecording();
}

void talkReleased() {
  if (gState != State::Recording) return;
  finishRecording();
}

bool busy() { return gState != State::Idle; }

void say(const char* text) {
  if (!text || !*text || gState != State::Idle) return;
  gState = State::Busy;
  ui::caption(text, 0);
  api::Error err = {};
  if (!api::speak(text, &err)) showError(err);
  ui::setActivity(gmini::Activity::Idle);
  ui::caption(text, captionMs(text));
  audio::micFlush();
  gState = State::Idle;
}

}  // namespace voice

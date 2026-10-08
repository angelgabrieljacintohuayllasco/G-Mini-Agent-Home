// Pruebas en el host de GMiniLink: base64, WAV, JSON y HTTP en flujo,
// enlaces de emparejamiento y detector de voz.
#include <GMiniLink.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <unity.h>

#include <string>
#include <vector>

using namespace gmini::link;

void setUp() {}
void tearDown() {}

namespace {

std::vector<uint8_t> gBytes;
std::string gChars;

void collectBytes(const uint8_t* d, size_t n, void*) { gBytes.insert(gBytes.end(), d, d + n); }
void collectChars(const char* d, size_t n, void*) { gChars.append(d, n); }

const char* kB64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string encodeBase64(const std::vector<uint8_t>& in) {
  std::string out;
  size_t i = 0;
  for (; i + 2 < in.size(); i += 3) {
    uint32_t v = (in[i] << 16) | (in[i + 1] << 8) | in[i + 2];
    out += kB64[(v >> 18) & 63];
    out += kB64[(v >> 12) & 63];
    out += kB64[(v >> 6) & 63];
    out += kB64[v & 63];
  }
  if (in.size() - i == 1) {
    uint32_t v = in[i] << 16;
    out += kB64[(v >> 18) & 63];
    out += kB64[(v >> 12) & 63];
    out += "==";
  } else if (in.size() - i == 2) {
    uint32_t v = (in[i] << 16) | (in[i + 1] << 8);
    out += kB64[(v >> 18) & 63];
    out += kB64[(v >> 12) & 63];
    out += kB64[(v >> 6) & 63];
    out += "=";
  }
  return out;
}

std::vector<uint8_t> makeWav(uint32_t rate, uint16_t samples, bool withList) {
  std::vector<uint8_t> pcm(samples * 2);
  for (uint16_t i = 0; i < samples; ++i) {
    int16_t s = (int16_t)(8000 * sin(i * 0.1));
    pcm[i * 2] = (uint8_t)s;
    pcm[i * 2 + 1] = (uint8_t)(s >> 8);
  }
  uint8_t hdr[44];
  buildWavHeader(hdr, rate, 1, 16, (uint32_t)pcm.size());
  std::vector<uint8_t> out(hdr, hdr + 36);
  if (withList) {  // chunk desconocido de tamano impar antes de data
    const uint8_t list[] = {'L', 'I', 'S', 'T', 3, 0, 0, 0, 'a', 'b', 'c', 0};
    out.insert(out.end(), list, list + sizeof(list));
  }
  out.insert(out.end(), hdr + 36, hdr + 44);
  out.insert(out.end(), pcm.begin(), pcm.end());
  return out;
}

struct WavCtx {
  WavFormat fmt;
  int formats;
};

void onFormat(const WavFormat& f, void* ctx) {
  WavCtx* c = static_cast<WavCtx*>(ctx);
  c->fmt = f;
  c->formats++;
}

}  // namespace

// ------------------------------------------------------------------ base64

void test_base64_roundtrip_any_split() {
  std::vector<uint8_t> data;
  for (int i = 0; i < 1000; ++i) data.push_back((uint8_t)(i * 37 + 11));
  for (size_t trim = 0; trim < 3; ++trim) {
    std::vector<uint8_t> in(data.begin(), data.end() - trim);
    std::string enc = encodeBase64(in);
    for (size_t step : {1u, 3u, 7u, 64u, 5000u}) {
      gBytes.clear();
      Base64Decoder d(collectBytes, nullptr);
      for (size_t i = 0; i < enc.size(); i += step) d.feed(enc.data() + i, std::min(step, enc.size() - i));
      TEST_ASSERT_TRUE(d.finish());
      TEST_ASSERT_EQUAL_UINT32(in.size(), gBytes.size());
      TEST_ASSERT_EQUAL_MEMORY(in.data(), gBytes.data(), in.size());
    }
  }
}

void test_base64_ignores_whitespace_and_flags_garbage() {
  gBytes.clear();
  Base64Decoder d(collectBytes, nullptr);
  d.feed("SG9s\nYQ==", 9);
  TEST_ASSERT_TRUE(d.finish());
  TEST_ASSERT_EQUAL_UINT32(4, gBytes.size());
  TEST_ASSERT_EQUAL_MEMORY("Hola", gBytes.data(), 4);
  Base64Decoder bad(collectBytes, nullptr);
  bad.feed("SG*s", 4);
  bad.finish();
  TEST_ASSERT_TRUE(bad.error());
}

// ------------------------------------------------------------------ WAV

void test_wav_header_and_pcm() {
  std::vector<uint8_t> wav = makeWav(22050, 500, true);
  for (size_t step : {1u, 5u, 44u, 4096u}) {
    gBytes.clear();
    WavCtx ctx = {};
    WavDecoder w(onFormat, collectBytes, &ctx);
    for (size_t i = 0; i < wav.size(); i += step) w.feed(wav.data() + i, std::min(step, wav.size() - i));
    TEST_ASSERT_FALSE(w.error());
    TEST_ASSERT_TRUE(w.ready());
    TEST_ASSERT_EQUAL_INT(1, ctx.formats);
    TEST_ASSERT_EQUAL_UINT32(22050, ctx.fmt.sampleRate);
    TEST_ASSERT_EQUAL_UINT16(1, ctx.fmt.channels);
    TEST_ASSERT_EQUAL_UINT16(16, ctx.fmt.bitsPerSample);
    TEST_ASSERT_EQUAL_UINT32(1000, gBytes.size());
    TEST_ASSERT_EQUAL_MEMORY(wav.data() + wav.size() - 1000, gBytes.data(), 1000);
  }
}

void test_wav_rejects_non_wav_and_supports_raw() {
  WavDecoder w(nullptr, collectBytes, nullptr);
  const uint8_t junk[] = "<html>not audio</html>";
  w.feed(junk, sizeof(junk));
  TEST_ASSERT_TRUE(w.error());

  gBytes.clear();
  WavCtx ctx = {};
  WavDecoder raw(onFormat, collectBytes, &ctx);
  raw.setRaw(16000, 1);
  const uint8_t pcm[] = {1, 2, 3, 4};
  raw.feed(pcm, 4);
  TEST_ASSERT_EQUAL_UINT32(16000, ctx.fmt.sampleRate);
  TEST_ASSERT_EQUAL_UINT32(4, gBytes.size());
}

void test_build_wav_header() {
  uint8_t h[44];
  TEST_ASSERT_EQUAL_UINT32(44, buildWavHeader(h, 16000, 1, 16, 32000));
  TEST_ASSERT_EQUAL_MEMORY("RIFF", h, 4);
  TEST_ASSERT_EQUAL_UINT8(0x24, h[4]);  // 36 + 32000 = 32036 = 0x7D24
  TEST_ASSERT_EQUAL_UINT8(0x7D, h[5]);
  TEST_ASSERT_EQUAL_UINT8(0x80, h[24]);  // 16000 = 0x3E80
  TEST_ASSERT_EQUAL_UINT8(0x3E, h[25]);
  TEST_ASSERT_EQUAL_UINT8(0x00, h[28]);  // 32000 bytes/s = 0x7D00
  TEST_ASSERT_EQUAL_UINT8(0x7D, h[29]);
}

// ------------------------------------------------------------------ JSON

void test_json_voice_turn_fields() {
  const char* json =
      "{\"transcript\": \"qu\\u00e9 clima hace\", \"reply\": \"Soleado, 19 \\u00b0C.\\nListo\", "
      "\"session_id\": \"ses_1\", \"emotion\":\"happy\", \"actions\": [{\"reply\": \"x\"}], "
      "\"audio_mime\": \"audio/wav\", \"audio_base64\": \"SG9s\\/YQ==\", \"wake\": true, \"n\": 12.5}";
  char transcript[64], reply[64], emotion[16], session[16], wake[8], n[8];
  for (size_t step : {1u, 2u, 13u, 1000u}) {
    gChars.clear();
    JsonScanner s;
    s.addField("transcript", transcript, sizeof(transcript));
    s.addField("reply", reply, sizeof(reply));
    s.addField("emotion", emotion, sizeof(emotion));
    s.addField("session_id", session, sizeof(session));
    s.addField("wake", wake, sizeof(wake));
    s.addField("n", n, sizeof(n));
    s.setStreamField("audio_base64", collectChars, nullptr);
    const size_t len = strlen(json);
    for (size_t i = 0; i < len; i += step) s.feed(json + i, std::min(step, len - i));
    TEST_ASSERT_FALSE(s.error());
    TEST_ASSERT_TRUE(s.complete());
    TEST_ASSERT_EQUAL_STRING("qu\xC3\xA9 clima hace", transcript);
    TEST_ASSERT_EQUAL_STRING("Soleado, 19 \xC2\xB0" "C.\nListo", reply);
    TEST_ASSERT_EQUAL_STRING("happy", emotion);
    TEST_ASSERT_EQUAL_STRING("ses_1", session);
    TEST_ASSERT_EQUAL_STRING("true", wake);
    TEST_ASSERT_EQUAL_STRING("12.5", n);
    TEST_ASSERT_EQUAL_STRING("SG9s/YQ==", gChars.c_str());
  }
}

void test_json_error_object_and_truncation() {
  const char* json = "{\"error\": {\"code\": \"invalid_token\", \"message\": \"Token inv\\u00e1lido o revocado\"}}";
  char code[32], message[12];
  JsonScanner s;
  s.addField("code", code, sizeof(code), "error");
  s.addField("message", message, sizeof(message), "error");
  s.feed(json, strlen(json));
  TEST_ASSERT_FALSE(s.error());
  TEST_ASSERT_EQUAL_STRING("invalid_token", code);
  TEST_ASSERT_TRUE(s.found("message"));
  TEST_ASSERT_TRUE(s.truncated("message"));
  TEST_ASSERT_EQUAL_UINT32(11, strlen(message));
}

void test_json_surrogates_and_bad_input() {
  const char* json = "{\"reply\": \"ok \\ud83d\\ude00 fin\"}";
  char reply[32];
  JsonScanner s;
  s.addField("reply", reply, sizeof(reply));
  s.feed(json, strlen(json));
  TEST_ASSERT_EQUAL_STRING("ok \xF0\x9F\x98\x80 fin", reply);

  JsonScanner bad;
  bad.feed("{\"a\" 1}", 7);
  TEST_ASSERT_TRUE(bad.error());
}

// ------------------------------------------------------------------ HTTP

void test_http_content_length_body() {
  const char* resp =
      "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\nContent-Length: 11\r\n\r\n{\"ok\":true}EXTRA";
  gBytes.clear();
  HttpResponseParser p(collectBytes, nullptr);
  p.feed((const uint8_t*)resp, strlen(resp));
  TEST_ASSERT_TRUE(p.done());
  TEST_ASSERT_EQUAL_INT(200, p.status());
  TEST_ASSERT_EQUAL_STRING("application/json", p.contentType());
  TEST_ASSERT_EQUAL_UINT32(11, gBytes.size());
  TEST_ASSERT_EQUAL_MEMORY("{\"ok\":true}", gBytes.data(), 11);
}

void test_http_chunked_split_bytes() {
  const char* resp =
      "HTTP/1.1 409 Conflict\r\nTransfer-Encoding: chunked\r\n\r\n"
      "5\r\n{\"err\r\nA;ext=1\r\nor\": \"busy\r\n2\r\n\"}\r\n0\r\n\r\n";
  gBytes.clear();
  HttpResponseParser p(collectBytes, nullptr);
  const size_t len = strlen(resp);
  for (size_t i = 0; i < len; ++i) p.feed((const uint8_t*)resp + i, 1);
  TEST_ASSERT_TRUE(p.done());
  TEST_ASSERT_EQUAL_INT(409, p.status());
  TEST_ASSERT_TRUE(p.chunked());
  std::string body(gBytes.begin(), gBytes.end());
  TEST_ASSERT_EQUAL_STRING("{\"error\": \"busy\"}", body.c_str());
}

void test_http_close_delimited_and_garbage() {
  const char* resp = "HTTP/1.0 200 OK\r\n\r\nabc";
  gBytes.clear();
  HttpResponseParser p(collectBytes, nullptr);
  p.feed((const uint8_t*)resp, strlen(resp));
  TEST_ASSERT_FALSE(p.done());
  p.connectionClosed();
  TEST_ASSERT_TRUE(p.done());
  TEST_ASSERT_EQUAL_UINT32(3, gBytes.size());

  HttpResponseParser bad(collectBytes, nullptr);
  bad.feed((const uint8_t*)"SSH-2.0-OpenSSH\r\n", 17);
  TEST_ASSERT_TRUE(bad.error());
}

void test_full_voice_turn_pipeline() {
  // HTTP chunked -> JSON -> base64 -> WAV -> PCM, alimentado de a pocos bytes.
  std::vector<uint8_t> wav = makeWav(16000, 800, false);
  std::string json = "{\"transcript\":\"hola\",\"reply\":\"Hola\",\"emotion\":\"happy\",\"audio_base64\":\"" +
                     encodeBase64(wav) + "\"}";
  std::string http = "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n";
  for (size_t i = 0; i < json.size(); i += 333) {
    std::string part = json.substr(i, 333);
    char size[16];
    snprintf(size, sizeof(size), "%zx\r\n", part.size());
    http += size + part + "\r\n";
  }
  http += "0\r\n\r\n";

  gBytes.clear();
  WavCtx wctx = {};
  WavDecoder wavDec(onFormat, collectBytes, &wctx);
  Base64Decoder b64([](const uint8_t* d, size_t n, void* c) { static_cast<WavDecoder*>(c)->feed(d, n); }, &wavDec);
  JsonScanner json2;
  char emotion[16];
  json2.addField("emotion", emotion, sizeof(emotion));
  json2.setStreamField("audio_base64", [](const char* d, size_t n, void* c) { static_cast<Base64Decoder*>(c)->feed(d, n); },
                       &b64);
  HttpResponseParser p([](const uint8_t* d, size_t n, void* c) { static_cast<JsonScanner*>(c)->feed((const char*)d, n); },
                       &json2);
  for (size_t i = 0; i < http.size(); i += 17) p.feed((const uint8_t*)http.data() + i, std::min<size_t>(17, http.size() - i));
  TEST_ASSERT_TRUE(b64.finish());
  TEST_ASSERT_TRUE(p.done());
  TEST_ASSERT_TRUE(json2.complete());
  TEST_ASSERT_EQUAL_STRING("happy", emotion);
  TEST_ASSERT_EQUAL_UINT32(16000, wctx.fmt.sampleRate);
  TEST_ASSERT_EQUAL_UINT32(1600, gBytes.size());
  TEST_ASSERT_EQUAL_MEMORY(wav.data() + 44, gBytes.data(), 1600);
}

// ------------------------------------------------------------------ emparejamiento y URL

void test_pair_input() {
  PairInfo p;
  TEST_ASSERT_TRUE(parsePairInput(" 482913 ", &p));
  TEST_ASSERT_EQUAL_STRING("482913", p.code);
  TEST_ASSERT_EQUAL_UINT16(0, p.port);
  TEST_ASSERT_TRUE(parsePairInput("482-913", &p));
  TEST_ASSERT_EQUAL_STRING("482913", p.code);
  TEST_ASSERT_TRUE(parsePairInput("gmini://pair?host=100.64.0.10&port=8765&code=482913", &p));
  TEST_ASSERT_EQUAL_STRING("100.64.0.10", p.host);
  TEST_ASSERT_EQUAL_UINT16(8765, p.port);
  TEST_ASSERT_EQUAL_STRING("482913", p.code);
  TEST_ASSERT_TRUE(parsePairInput("GMINI://pair?code=111222&host=tv%2Dserver", &p));
  TEST_ASSERT_EQUAL_STRING("tv-server", p.host);
  TEST_ASSERT_FALSE(parsePairInput("48291", &p));
  TEST_ASSERT_FALSE(parsePairInput("4829134", &p));
  TEST_ASSERT_FALSE(parsePairInput("abc123", &p));
  TEST_ASSERT_FALSE(parsePairInput("gmini://pair?host=x&port=99999&code=482913", &p));
  TEST_ASSERT_FALSE(parsePairInput("gmini://pair", &p));
}

void test_server_url() {
  ServerAddr a;
  TEST_ASSERT_TRUE(parseServerUrl("192.168.1.20", &a));
  TEST_ASSERT_EQUAL_STRING("192.168.1.20", a.host);
  TEST_ASSERT_EQUAL_UINT16(8765, a.port);
  TEST_ASSERT_FALSE(a.tls);
  TEST_ASSERT_TRUE(parseServerUrl("http://tv-server:9000/", &a));
  TEST_ASSERT_EQUAL_STRING("tv-server", a.host);
  TEST_ASSERT_EQUAL_UINT16(9000, a.port);
  TEST_ASSERT_TRUE(parseServerUrl("https://gmini.example.com", &a));
  TEST_ASSERT_TRUE(a.tls);
  TEST_ASSERT_EQUAL_UINT16(443, a.port);
  TEST_ASSERT_FALSE(parseServerUrl("", &a));
  TEST_ASSERT_FALSE(parseServerUrl("host:0", &a));
  TEST_ASSERT_FALSE(parseServerUrl("ho st", &a));
  TEST_ASSERT_FALSE(parseServerUrl("host:12ab", &a));
}

// ------------------------------------------------------------------ detector de voz

void test_vad_detects_speech_and_end() {
  EnergyVad vad(16000);
  int16_t block[320];  // 20 ms
  uint32_t seed = 1;
  auto noise = [&](int amp) {
    for (int i = 0; i < 320; ++i) {
      seed = seed * 1103515245u + 12345u;
      block[i] = (int16_t)(((int)((seed >> 16) % (2 * amp + 1))) - amp);
    }
  };
  int starts = 0, ends = 0;
  for (int i = 0; i < 50; ++i) {  // 1 s de ruido de fondo
    noise(60);
    if (vad.feed(block, 320) != EnergyVad::kNone) ++starts;
  }
  TEST_ASSERT_EQUAL_INT(0, starts);
  for (int i = 0; i < 40; ++i) {  // 0,8 s de voz
    for (int k = 0; k < 320; ++k) block[k] = (int16_t)(4000 * sin((i * 320 + k) * 0.05));
    EnergyVad::Event e = vad.feed(block, 320);
    if (e == EnergyVad::kSpeechStart) ++starts;
  }
  TEST_ASSERT_EQUAL_INT(1, starts);
  TEST_ASSERT_TRUE(vad.inSpeech());
  for (int i = 0; i < 50; ++i) {
    noise(60);
    if (vad.feed(block, 320) == EnergyVad::kSpeechEnd) ++ends;
  }
  TEST_ASSERT_EQUAL_INT(1, ends);
  TEST_ASSERT_FALSE(vad.inSpeech());
}

void test_vad_caps_long_speech() {
  EnergyVad vad(16000);
  vad.maxSpeechMs = 1000;
  int16_t block[320];
  for (int k = 0; k < 320; ++k) block[k] = 0;
  for (int i = 0; i < 10; ++i) vad.feed(block, 320);
  for (int k = 0; k < 320; ++k) block[k] = (int16_t)(5000 * sin(k * 0.07));
  int ends = 0;
  for (int i = 0; i < 100; ++i) ends += vad.feed(block, 320) == EnergyVad::kSpeechEnd;
  TEST_ASSERT_TRUE(ends >= 1);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_base64_roundtrip_any_split);
  RUN_TEST(test_base64_ignores_whitespace_and_flags_garbage);
  RUN_TEST(test_wav_header_and_pcm);
  RUN_TEST(test_wav_rejects_non_wav_and_supports_raw);
  RUN_TEST(test_build_wav_header);
  RUN_TEST(test_json_voice_turn_fields);
  RUN_TEST(test_json_error_object_and_truncation);
  RUN_TEST(test_json_surrogates_and_bad_input);
  RUN_TEST(test_http_content_length_body);
  RUN_TEST(test_http_chunked_split_bytes);
  RUN_TEST(test_http_close_delimited_and_garbage);
  RUN_TEST(test_full_voice_turn_pipeline);
  RUN_TEST(test_pair_input);
  RUN_TEST(test_server_url);
  RUN_TEST(test_vad_detects_speech_and_end);
  RUN_TEST(test_vad_caps_long_speech);
  return UNITY_END();
}

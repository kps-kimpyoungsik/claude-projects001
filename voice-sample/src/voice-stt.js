/**
 * VoiceSTT v4.0 — ScriptProcessorNode 기반 Raw PCM 직접 수집
 *
 * v3 문제 해결:
 *  - MediaRecorder WebM 조각 → decodeAudioData 실패 제거
 *  - Pre-buffer 헤더 유실 문제 제거
 *  - ScriptProcessorNode로 raw Float32 PCM 직접 수집 → WAV 즉시 인코딩
 *
 * 동작 원리:
 *  1. ScriptProcessorNode가 4096 샘플 단위로 PCM 청크 수집
 *  2. 무음 중: PCM 청크를 Pre-Buffer(롤링)에 보관
 *  3. VAD 감지 → Pre-Buffer + 이후 청크를 Active Buffer에 누적
 *  4. 침묵 확정 → Float32 병합 → WAV 인코딩 → onAudioReady
 *  5. 최대 크기 초과 시 Seamless 분할 (녹음 중단 없음)
 */

const VoiceSTT = (() => {
  'use strict';

  // ── 기본 설정 ────────────────────────────────────────────────
  const DEFAULTS = {
    silenceThreshold : 0.012,
    silenceDuration  : 800,
    minSpeechMs      : 500,
    preBufMs         : 600,    // 발화 직전 보존 (ms)
    maxSegmentMB     : 0.5,    // 세그먼트당 최대 크기 MB (0.5MB = ~8초)
    sampleRate       : 16000,
    gainBoost        : 1.5,
    onAudioReady     : null,   // (wavBuffer: ArrayBuffer, durationMs: number) => void
    onStatus         : null,   // (state: string) => void
    onError          : null,   // (msg: string) => void
    onVAD            : null,   // (speaking: bool, rms: number) => void
  };

  let cfg = { ...DEFAULTS };

  // ── 내부 상태 ────────────────────────────────────────────────
  let state        = 'idle';
  let mediaStream  = null;
  let audioCtx     = null;
  let analyser     = null;
  let scriptProc   = null;
  let animId       = null;

  // Pre-Buffer: 항상 최근 preBufMs 분의 PCM 청크를 롤링 보관
  let preBuf        = [];   // Float32Array[]
  let preBufSamples = 0;
  let preBufMaxSamples = 0;

  // Active Buffer: 발화 중 누적
  let activeBuf        = [];   // Float32Array[]
  let activeSamples    = 0;
  let maxActiveSamples = 0;

  let isSpeaking    = false;
  let speechStartMs = 0;
  let speechEndMs   = 0;
  let silTimer      = null;

  // ── 공개 API ─────────────────────────────────────────────────

  function init(options = {}) {
    cfg = { ...DEFAULTS, ...options };
    // preBufMs → 샘플 수 변환 (float32)
    preBufMaxSamples = Math.floor(cfg.preBufMs / 1000 * cfg.sampleRate);
    // maxSegmentMB → 샘플 수 (float32 = 4 bytes/sample)
    maxActiveSamples = cfg.maxSegmentMB > 0
      ? Math.floor(cfg.maxSegmentMB * 1024 * 1024 / 4)
      : 0;
  }

  async function start() {
    if (state !== 'idle') return;
    _setState('connecting');
    try {
      await _openMic();
      _startLoop();
      _setState('ready');
    } catch (e) {
      _setState('idle');
      _err('마이크 접근 실패: ' + e.message);
    }
  }

  function stop() {
    _finalizeSpeech(true);
    _cleanup();
    _setState('idle');
  }

  function getState()    { return state; }
  function getAnalyser() { return analyser; }

  // 실시간 버퍼 상태 조회 (시각화 페이지용)
  function getStats() {
    const bytesPerSample = 4; // Float32
    return {
      preBufKB    : (preBufSamples  * bytesPerSample / 1024).toFixed(1),
      activeBufKB : (activeSamples  * bytesPerSample / 1024).toFixed(1),
      preBufMs    : (preBufSamples  / cfg.sampleRate * 1000).toFixed(0),
      activeBufMs : (activeSamples  / cfg.sampleRate * 1000).toFixed(0),
      isSpeaking,
    };
  }

  // ── 마이크 + 오디오 처리 체인 ────────────────────────────────

  async function _openMic() {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount    : 1,
        sampleRate      : cfg.sampleRate,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl : true,
      },
      video: false,
    });

    audioCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: cfg.sampleRate,
    });

    const source = audioCtx.createMediaStreamSource(mediaStream);

    // 노이즈 보정 체인: HPF → Compressor → Gain → Analyser
    const hpf = audioCtx.createBiquadFilter();
    hpf.type = 'highpass';
    hpf.frequency.value = 80;
    hpf.Q.value = 0.7;

    const comp = audioCtx.createDynamicsCompressor();
    comp.threshold.value = -40;
    comp.knee.value      = 15;
    comp.ratio.value     = 6;
    comp.attack.value    = 0.005;
    comp.release.value   = 0.15;

    const gain = audioCtx.createGain();
    gain.gain.value = Math.max(1.0, cfg.gainBoost);

    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 1024;

    source.connect(hpf);
    hpf.connect(comp);
    comp.connect(gain);
    gain.connect(analyser);

    // ScriptProcessorNode: raw PCM 수집 (WebM 변환 없음)
    // 4096 샘플 = 16kHz 기준 약 256ms
    scriptProc = audioCtx.createScriptProcessor(4096, 1, 1);
    gain.connect(scriptProc);
    scriptProc.connect(audioCtx.destination); // 출력 연결 필수

    scriptProc.onaudioprocess = e => {
      if (state === 'idle') return;
      const pcm = e.inputBuffer.getChannelData(0).slice(); // Float32Array 복사

      if (isSpeaking) {
        activeBuf.push(pcm);
        activeSamples += pcm.length;

        // Seamless 분할: 최대 크기 초과 시 현재 버퍼 비동기 플러시
        if (maxActiveSamples > 0 && activeSamples >= maxActiveSamples) {
          const chunks  = activeBuf.slice();
          const segMs   = Date.now() - speechStartMs;
          activeBuf     = [];
          activeSamples = 0;
          speechStartMs = Date.now();
          speechEndMs   = 0;
          _sendPCM(chunks, segMs);
        }
      } else {
        // Pre-Buffer 롤링: 최신 preBufMs 분만 보관
        preBuf.push(pcm);
        preBufSamples += pcm.length;
        while (preBufSamples > preBufMaxSamples && preBuf.length > 0) {
          preBufSamples -= preBuf.shift().length;
        }
      }
    };
  }

  // ── 메인 루프 (VAD) ───────────────────────────────────────────

  function _startLoop() {
    const buf = new Uint8Array(analyser.frequencyBinCount);

    function tick() {
      if (state === 'idle') return;
      animId = requestAnimationFrame(tick);

      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buf.length);
      cfg.onVAD && cfg.onVAD(rms > cfg.silenceThreshold, rms);

      if (rms > cfg.silenceThreshold) {
        if (!isSpeaking) {
          isSpeaking    = true;
          speechStartMs = Date.now();
          // Pre-Buffer → Active Buffer 이관
          activeBuf     = preBuf.slice();
          activeSamples = preBufSamples;
          preBuf        = [];
          preBufSamples = 0;
        }
        if (silTimer) { clearTimeout(silTimer); silTimer = null; }
      } else {
        if (isSpeaking && !silTimer) {
          speechEndMs = Date.now();
          silTimer = setTimeout(_onSilence, cfg.silenceDuration);
        }
      }
    }

    tick();
  }

  function _onSilence() {
    silTimer   = null;
    isSpeaking = false;
    _finalizeSpeech(false);
  }

  function _finalizeSpeech(force) {
    if (activeBuf.length === 0) return;

    const end      = speechEndMs > 0 ? speechEndMs : Date.now();
    const speechMs = end - speechStartMs;
    const chunks   = activeBuf.slice();

    activeBuf     = [];
    activeSamples = 0;
    speechStartMs = 0;
    speechEndMs   = 0;

    if (!force && speechMs < cfg.minSpeechMs) return;

    _sendPCM(chunks, speechMs);
  }

  // ── PCM 처리 + WAV 인코딩 ─────────────────────────────────────

  function _sendPCM(chunks, speechMs) {
    // Float32Array 청크 병합
    const totalSamples = chunks.reduce((s, c) => s + c.length, 0);
    if (totalSamples === 0) return;

    const merged = new Float32Array(totalSamples);
    let offset = 0;
    for (const c of chunks) {
      merged.set(c, offset);
      offset += c.length;
    }

    // 무음 구간 트리밍
    const trimmed = _trimSilence(merged);
    if (!trimmed) return;

    const actualMs = trimmed.length / cfg.sampleRate * 1000;
    if (actualMs < cfg.minSpeechMs) return;

    const wav = _encodeWAV(trimmed, cfg.sampleRate);
    cfg.onAudioReady && cfg.onAudioReady(wav, Math.round(actualMs));
  }

  // ── 오디오 유틸 ──────────────────────────────────────────────

  function _trimSilence(pcm) {
    const thr = cfg.silenceThreshold;
    const pad = Math.floor(cfg.sampleRate * 0.1);
    let s = -1;
    for (let i = 0; i < pcm.length; i++) {
      if (Math.abs(pcm[i]) > thr) { s = i; break; }
    }
    if (s < 0) return null;
    let e = s;
    for (let i = pcm.length - 1; i > s; i--) {
      if (Math.abs(pcm[i]) > thr) { e = i; break; }
    }
    return pcm.subarray(Math.max(0, s - pad), Math.min(pcm.length, e + pad + 1));
  }

  function _encodeWAV(samples, sr) {
    const n   = samples.length;
    const buf = new ArrayBuffer(44 + n * 2);
    const v   = new DataView(buf);
    const ws  = (off, str) => { for (let i = 0; i < str.length; i++) v.setUint8(off + i, str.charCodeAt(i)); };
    ws(0,  'RIFF'); v.setUint32(4,  36 + n * 2, true);
    ws(8,  'WAVE'); ws(12, 'fmt ');
    v.setUint32(16, 16,      true);
    v.setUint16(20,  1,      true); // PCM
    v.setUint16(22,  1,      true); // mono
    v.setUint32(24, sr,      true);
    v.setUint32(28, sr * 2,  true); // byteRate
    v.setUint16(32,  2,      true); // blockAlign
    v.setUint16(34, 16,      true); // bitsPerSample
    ws(36, 'data'); v.setUint32(40, n * 2, true);
    let off = 44;
    for (let i = 0; i < n; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      off += 2;
    }
    return buf;
  }

  // ── 정리 ─────────────────────────────────────────────────────

  function _cleanup() {
    if (animId)     { cancelAnimationFrame(animId); animId = null; }
    if (scriptProc) { scriptProc.disconnect(); scriptProc = null; }
    if (mediaStream){ mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
    if (audioCtx)   { audioCtx.close(); audioCtx = null; }
    if (silTimer)   { clearTimeout(silTimer); silTimer = null; }
    preBuf        = []; preBufSamples  = 0;
    activeBuf     = []; activeSamples  = 0;
    isSpeaking    = false;
    speechStartMs = 0;  speechEndMs    = 0;
  }

  function _setState(s) { state = s; cfg.onStatus && cfg.onStatus(s); }
  function _err(msg)    { cfg.onError && cfg.onError(msg); }

  // ── 공개 인터페이스 ───────────────────────────────────────────
  return { init, start, stop, getState, getAnalyser, getStats };
})();

if (typeof window !== 'undefined') window.VoiceSTT = VoiceSTT;

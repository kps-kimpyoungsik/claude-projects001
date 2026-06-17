package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gorilla/websocket"
)

const (
	recBase    = "recordings"
	numWorkers = 2 // go-whisper contextPool 개념: 병렬 STT 워커 수
	maxRetries = 2 // 자동 재시도 횟수 (실패 시 처리대기)
)

// ── 저장 모드 ────────────────────────────────────────────────
// SAVE_MODE 환경변수로 파일 저장 방식을 선택한다.
//
//	memory  (기본) A안: WAV/TXT 파일 없음, STT 결과를 메모리에만 보관
//	                   - 서버 재시작 시 결과 초기화
//	                   - 디스크 사용 없음
//	text           B안: WAV 없음, TXT만 저장
//	                   - STT 결과를 recordings/{topic}/*.txt 에 저장
//	                   - 서버 재시작 후에도 텍스트 유지
//	                   - batch_stt.py 등 후처리 파이프라인 연동 가능
//	full           원래 방식: WAV + TXT + SRT 모두 저장
//	                   - 완전한 파일 보관
//	                   - 재처리(retranscribe) 가능

type SaveMode string

const (
	SaveModeMemory SaveMode = "memory" // A안
	SaveModeText   SaveMode = "text"   // B안
	SaveModeFull   SaveMode = "full"   // 원래 방식
)

func loadSaveMode() SaveMode {
	switch strings.ToLower(os.Getenv("SAVE_MODE")) {
	case "text":
		return SaveModeText
	case "full":
		return SaveModeFull
	default:
		return SaveModeMemory
	}
}

var saveMode = loadSaveMode()

// ── 자동 요약 설정 ──────────────────────────────────────────
// AUTO_SUMMARY=0   비활성화 (수동 POST /api/summary 필요)
// AUTO_SUMMARY=1   활성화 (기본) — 녹음 종료 시 자동 요약 시작
// SUMMARY_DOCTYPE  md (기본) / docx / pdf / xlsx / pptx
var autoSummaryEnabled = os.Getenv("AUTO_SUMMARY") != "0"

func getSummaryDoctype() string {
	if d := os.Getenv("SUMMARY_DOCTYPE"); d != "" {
		return d
	}
	return "md"
}

// ── WAV 사후 처리 정책 ────────────────────────────────────────
// STT 완료 후 원본 .wav 파일을 어떻게 처리할지 (SaveModeFull 한정).
//   keep   (기본) 원본 그대로 유지
//   delete STT 완료 즉시 원본 삭제 (디스크 절약)
//   backup {topic}/_wav_backup/ 로 이동 (검증 후 일괄 삭제 가능)
type WavCleanup string

const (
	WavCleanupKeep   WavCleanup = "keep"
	WavCleanupDelete WavCleanup = "delete"
	WavCleanupBackup WavCleanup = "backup"
)

func loadWavCleanup() WavCleanup {
	switch strings.ToLower(os.Getenv("WAV_CLEANUP")) {
	case "delete":
		return WavCleanupDelete
	case "backup":
		return WavCleanupBackup
	default:
		return WavCleanupKeep
	}
}

var (
	wavCleanup   = loadWavCleanup()
	wavCleanupMu sync.Mutex
)

// ── 트랜스크립트 병합 정책 ────────────────────────────────────
// 여러 개 WAV 파일의 텍스트를 transcript.txt로 합칠 시점:
//   auto   (기본) 녹음 종료 시 자동으로 병합
//   manual 수동으로 "/api/transcript/merge" 버튼 클릭 시 병합
type TranscriptMode string

const (
	TranscriptModeAuto   TranscriptMode = "auto"
	TranscriptModeManual TranscriptMode = "manual"
)

func loadTranscriptMode() TranscriptMode {
	switch strings.ToLower(os.Getenv("TRANSCRIPT_MODE")) {
	case "manual":
		return TranscriptModeManual
	default:
		return TranscriptModeAuto
	}
}

var (
	transcriptMode   = loadTranscriptMode()
	transcriptModeMu sync.Mutex
)

func getTranscriptMode() TranscriptMode {
	transcriptModeMu.Lock()
	defer transcriptModeMu.Unlock()
	return transcriptMode
}

func setTranscriptMode(v TranscriptMode) {
	transcriptModeMu.Lock()
	transcriptMode = v
	transcriptModeMu.Unlock()
}

func getWavCleanup() WavCleanup {
	wavCleanupMu.Lock()
	defer wavCleanupMu.Unlock()
	return wavCleanup
}

func setWavCleanup(v WavCleanup) {
	wavCleanupMu.Lock()
	wavCleanup = v
	wavCleanupMu.Unlock()
}

// applyWavCleanup: STT 완료 후 원본 WAV에 정책 적용 (full 모드 한정)
func applyWavCleanup(topic, filename string) {
	if saveMode != SaveModeFull {
		return
	}
	policy := getWavCleanup()
	if policy == WavCleanupKeep {
		return
	}
	src := filepath.Join(recBase, topic, filename)
	if _, err := os.Stat(src); err != nil {
		return
	}
	switch policy {
	case WavCleanupDelete:
		if err := os.Remove(src); err != nil {
			fmt.Printf("[wav-cleanup] delete 실패 %s: %v\n", filename, err)
		}
	case WavCleanupBackup:
		backupDir := filepath.Join(recBase, topic, "_wav_backup")
		os.MkdirAll(backupDir, 0755)
		dst := filepath.Join(backupDir, filename)
		if err := os.Rename(src, dst); err != nil {
			fmt.Printf("[wav-cleanup] backup 실패 %s: %v\n", filename, err)
		}
	}
}

// ── STT 시나리오 프리셋 (런타임 변경 가능) ───────────────────────
// STT_SCENARIO 환경변수로 초기값 설정. /api/scenario POST로 재시작 없이 변경.
//   quiet     조용한 회의실 (기본)
//   noisy     시끄러운 환경
//   interview 1:1 인터뷰
//   debate    다자 토론
//   phone     전화 녹음

var (
	activeScenario   = loadScenario()
	activeScenarioMu sync.Mutex
)

func loadScenario() string {
	s := strings.ToLower(os.Getenv("STT_SCENARIO"))
	valid := map[string]bool{"quiet": true, "noisy": true, "interview": true, "debate": true, "phone": true}
	if valid[s] {
		return s
	}
	return "quiet"
}

func getScenario() string {
	activeScenarioMu.Lock()
	defer activeScenarioMu.Unlock()
	return activeScenario
}

func setScenario(s string) bool {
	valid := map[string]bool{"quiet": true, "noisy": true, "interview": true, "debate": true, "phone": true}
	if !valid[s] {
		return false
	}
	activeScenarioMu.Lock()
	activeScenario = s
	activeScenarioMu.Unlock()
	return true
}

// ── 환경변수 기반 런타임 설정 ─────────────────────────────────
// 환경변수로 덮어쓸 수 있는 클라이언트 설정값.
// 서버 재시작 없이 .env 또는 OS 환경변수로 조정 가능.
//
//	MAX_FILE_MB         파일 크기 상한 (기본 5)
//	SILENCE_DURATION_MS 침묵 감지 시간 ms (기본 5000)
//	SILENCE_THRESHOLD   RMS 침묵 임계값 0~1 (기본 0.012)
//	MIN_SPEECH_MS       최소 발화 인정 시간 ms (기본 800)
type ClientConfig struct {
	MaxFileMB         float64 `json:"maxFileMB"`
	SilenceDurationMs int     `json:"silenceDuration"`
	SilenceThreshold  float64 `json:"silenceThreshold"`
	MinSpeechMs       int     `json:"minSpeechMs"`
}

func loadClientConfig() ClientConfig {
	cfg := ClientConfig{
		MaxFileMB:         0.5,   // 0.5MB 단위 저장
		SilenceDurationMs: 800,
		SilenceThreshold:  0.012,
		MinSpeechMs:       800,
	}
	if v := os.Getenv("MAX_FILE_MB"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil && f > 0 {
			cfg.MaxFileMB = f
		}
	}
	if v := os.Getenv("SILENCE_DURATION_MS"); v != "" {
		if i, err := strconv.Atoi(v); err == nil && i > 0 {
			cfg.SilenceDurationMs = i
		}
	}
	if v := os.Getenv("SILENCE_THRESHOLD"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil && f > 0 {
			cfg.SilenceThreshold = f
		}
	}
	if v := os.Getenv("MIN_SPEECH_MS"); v != "" {
		if i, err := strconv.Atoi(v); err == nil && i > 0 {
			cfg.MinSpeechMs = i
		}
	}
	return cfg
}

var clientCfg = loadClientConfig()

// go-whisper 분석 반영: 다중 인스턴스 라운드로빈 (contextPool 병렬화)
// STT_HOSTS 환경변수로 설정 가능 (쉼표 구분, 기본: localhost:9001,localhost:9002)
var (
	sttHosts = loadSTTHosts()
	sttIdx   int64  // atomic 라운드로빈 인덱스
)

func loadSTTHosts() []string {
	if v := os.Getenv("STT_HOSTS"); v != "" {
		hosts := []string{}
		for _, h := range strings.Split(v, ",") {
			h = strings.TrimSpace(h)
			if h != "" {
				if !strings.HasPrefix(h, "ws://") && !strings.HasPrefix(h, "wss://") {
					h = "ws://" + h
				}
				hosts = append(hosts, h)
			}
		}
		if len(hosts) > 0 {
			return hosts
		}
	}
	return []string{"ws://localhost:9001"}
}

func nextSTTHost() string {
	idx := atomic.AddInt64(&sttIdx, 1)
	return sttHosts[idx%int64(len(sttHosts))]
}

// hostForAttempt: 재시도 시 순서대로 다른 호스트 선택 (failover)
func hostForAttempt(attempt int) string {
	n := int64(len(sttHosts))
	// attempt 0은 nextSTTHost 사용, 이후는 다음 인덱스 강제 선택
	if attempt == 0 {
		return nextSTTHost()
	}
	idx := atomic.LoadInt64(&sttIdx) + int64(attempt)
	return sttHosts[idx%n]
}

// resultEntry: TTL 만료를 위한 타임스탬프 래퍼
type resultEntry struct {
	result    STTResult
	storedAt  time.Time
}

const resultTTL = 2 * time.Hour // 2시간 후 자동 만료

// ── 모니터링 / Headless 설정 ─────────────────────────────────
// HEADLESS=1       : Static 파일 서빙 OFF (API 전용 모드)
// API_KEY=<secret> : X-API-Key 헤더 또는 ?api_key= 파라미터로 인증
// WS_BROADCAST=0   : /ws/live 브로드캐스트 비활성 (API 전용 시 불필요)

type MonitorConfig struct {
	mu          sync.RWMutex
	Headless    bool   // true = UI 서빙 OFF
	WsBroadcast bool   // false = /ws/live 브로드캐스트 OFF
	apiKey      string // 빈 문자열 = 인증 없음
}

func (m *MonitorConfig) AuthRequired() bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.apiKey != ""
}

func (m *MonitorConfig) ValidKey(key string) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.apiKey == "" || m.apiKey == key
}

func (m *MonitorConfig) Get() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return map[string]interface{}{
		"headless":         m.Headless,
		"ws_broadcast":     m.WsBroadcast,
		"auth_required":    m.apiKey != "",
		"save_mode":        string(saveMode),
		"wav_cleanup":      string(getWavCleanup()),
		"transcript_mode":  string(getTranscriptMode()),
	}
}

func (m *MonitorConfig) Set(headless, wsBroadcast *bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if headless != nil    { m.Headless    = *headless }
	if wsBroadcast != nil { m.WsBroadcast = *wsBroadcast }
}

func loadMonitorConfig() *MonitorConfig {
	apiKey := os.Getenv("API_KEY")
	wsBroadcast := os.Getenv("WS_BROADCAST") != "0" // 기본 true
	headless := os.Getenv("HEADLESS") == "1"
	return &MonitorConfig{
		Headless:    headless,
		WsBroadcast: wsBroadcast,
		apiKey:      apiKey,
	}
}

var monitor = loadMonitorConfig()

// ── 파이프라인 상태 ───────────────────────────────────────────
// POST /api/summary 로 트리거, Go가 Python post_pipeline.py를 subprocess로 실행

type PipelineStatus string

const (
	PipelineIdle       PipelineStatus = "idle"
	PipelineRunning    PipelineStatus = "running"
	PipelineSummarizing PipelineStatus = "summarizing"
	PipelineGenerating PipelineStatus = "generating"
	PipelineDone       PipelineStatus = "done"
	PipelineError      PipelineStatus = "error"
)

type PipelineState struct {
	Status  PipelineStatus `json:"status"`
	Step    string         `json:"step,omitempty"`
	Message string         `json:"message,omitempty"`
	SumPath string         `json:"sum_path,omitempty"`
	DocPath string         `json:"doc_path,omitempty"`
	DocFile string         `json:"doc_file,omitempty"` // 파일명만 (다운로드 URL 구성용)
	Elapsed float64        `json:"elapsed,omitempty"`
	Error   string         `json:"error,omitempty"`
}

var pipelineMap sync.Map // topic → PipelineState

var (
	mu       sync.Mutex
	dataFile = "transcripts.jsonl"
	statusMap sync.Map // "topic::file" → queued|processing|done|처리대기
	resultMap sync.Map // "topic::file" → resultEntry (TTL 만료 관리)
	metaMap   sync.Map // "topic::file" → RecordingInfo (파일 목록용)
	sttQueue  = make(chan STTJob, 300)

	// 화자 정렬 트랜스크립트: 토픽별 엔트리 누적 후 파일명 순 정렬·화자 병합으로 재작성
	topicEntries   = make(map[string][]TranscriptEntry)
	topicEntriesMu sync.Mutex

	// ChunkBoundaryManager: 토픽별 미완성 문장 버퍼
	topicPending   = make(map[string]string)
	topicPendingMu sync.Mutex
)

// resultMapStore: TTL 타임스탬프와 함께 저장
func resultMapStore(key string, r STTResult) {
	resultMap.Store(key, resultEntry{result: r, storedAt: time.Now()})
}

// resultMapLoad: TTL 만료 시 nil 반환
func resultMapLoad(key string) (STTResult, bool) {
	v, ok := resultMap.Load(key)
	if !ok {
		return STTResult{}, false
	}
	e := v.(resultEntry)
	if time.Since(e.storedAt) > resultTTL {
		resultMap.Delete(key)
		return STTResult{}, false
	}
	return e.result, true
}

type STTJob struct {
	Topic    string
	Filename string
	WavBytes []byte // 메모리 전달 — 파일 저장 안 함
}

// go-whisper schema.Segment 대응 (SRT 생성용 + 화자 정보)
type STTSegment struct {
	Start   float64 `json:"start"`
	End     float64 `json:"end"`
	Text    string  `json:"text"`
	Speaker string  `json:"speaker,omitempty"` // 세그먼트별 화자 (옵션)
}

type STTResult struct {
	Text            string       `json:"text"`
	Segments        []STTSegment `json:"segments"`
	SpeakerSegments []STTSegment `json:"speaker_segments"` // 세그먼트별 화자 정보
	SegID           int          `json:"seg_id"`
	Speaker         string       `json:"speaker"`
	Similarity      float64      `json:"similarity"`
	IsKnown         bool         `json:"isKnown"`
}

// TranscriptEntry: 화자 정렬 트랜스크립트용 단위 항목
type TranscriptEntry struct {
	Filename string
	TimeStr  string
	Speaker  string
	Text     string
	Source   string // "whisper" | "browser" — Whisper 도착 시 browser 항목을 교체
}

type RecordingInfo struct {
	Filename  string `json:"filename"`
	Created   string `json:"created"`   // 음성 파일 생성 시간 (15:04:05)
	SizeKB    float64 `json:"sizeKB"`
	Status    string `json:"status"`   // queued|processing|done|처리대기
	HasText   bool   `json:"hasText"`
	HasSRT    bool   `json:"hasSrt"`
	CompletedAt string `json:"completedAt"` // 텍스트 변환 완료 시간 (15:04:05.000) — nil이면 미완료
}

type Entry struct {
	Time       string  `json:"time"`
	Speaker    string  `json:"speaker"`
	Text       string  `json:"text"`
	Similarity float64 `json:"similarity"`
	IsKnown    bool    `json:"isKnown"`
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// ── 실시간 결과 푸시 허브 (/ws/live) ──────────────────────────────

type liveHub struct {
	clients map[chan []byte]bool
	mu      sync.Mutex
}

var hub = &liveHub{clients: make(map[chan []byte]bool)}

func (h *liveHub) register(ch chan []byte) {
	h.mu.Lock()
	h.clients[ch] = true
	h.mu.Unlock()
}

func (h *liveHub) unregisterClose(ch chan []byte) {
	h.mu.Lock()
	delete(h.clients, ch)
	h.mu.Unlock()
	close(ch)
}

func (h *liveHub) broadcast(msg []byte) {
	h.mu.Lock()
	defer h.mu.Unlock()
	for ch := range h.clients {
		select {
		case ch <- msg:
		default: // 느린 클라이언트: 프레임 드랍
		}
	}
}

func (h *liveHub) HasClients() bool {
	h.mu.Lock()
	defer h.mu.Unlock()
	return len(h.clients) > 0
}

// broadcastJSON: WsBroadcast 활성 상태일 때만 직렬화 후 브로드캐스트
func broadcastJSON(v interface{}) {
	monitor.mu.RLock()
	enabled := monitor.WsBroadcast
	monitor.mu.RUnlock()
	if !enabled { return }
	if b, err := json.Marshal(v); err == nil {
		hub.broadcast(b)
	}
}

func handleLiveWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	ch := make(chan []byte, 32)
	hub.register(ch)
	defer hub.unregisterClose(ch)

	// 클라이언트 연결 끊김 감지
	done := make(chan struct{})
	go func() {
		defer close(done)
		for {
			if _, _, err := conn.ReadMessage(); err != nil {
				return
			}
		}
	}()

	for {
		select {
		case msg, ok := <-ch:
			if !ok {
				return
			}
			if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				return
			}
		case <-done:
			return
		}
	}
}

func init() {
	for i := 0; i < numWorkers; i++ {
		go sttWorker(i)
	}
	// STT 워커 워밍업: 서버 시작 시 더미 WAV 5개 미리 preload
	// → 모델 로딩 + 메모리 할당 완료하여 첫 실제 요청 시 3초 내 응답 가능
	go preloadSTTWorkers()

	go func() {
		ticker := time.NewTicker(6 * time.Hour)
		defer ticker.Stop()
		for range ticker.C {
			resultMap.Range(func(k, v interface{}) bool {
				if e, ok := v.(resultEntry); ok && time.Since(e.storedAt) > resultTTL {
					resultMap.Delete(k)
				}
				return true
			})
		}
	}()
}

// preloadSTTWorkers: 시작 시 더미 WAV 5개를 워커 큐에 넣어 워밍업
func preloadSTTWorkers() {
	time.Sleep(500 * time.Millisecond) // 워커 초기화 대기

	// 더미 WAV 생성 (1초 440Hz 사인파, 16kHz 16bit PCM)
	dummyWAV := generateDummyWAV(1.0, 440.0)

	for i := 0; i < 5; i++ {
		filename := fmt.Sprintf("warmup_%d.wav", i)
		select {
		case sttQueue <- STTJob{
			Topic:    "__warmup__",
			Filename: filename,
			WavBytes: dummyWAV,
		}:
			// 큐에 추가 성공
		case <-time.After(100 * time.Millisecond):
			// 타임아웃 시 건너뛰기
		}
	}
	fmt.Printf("[init] STT 워커 워밍업: 더미 WAV 5개 전송\n")
}

// generateDummyWAV: 간단한 사인파 WAV 생성
func generateDummyWAV(durationSec float64, freqHz float64) []byte {
	sr := 16000 // 16kHz
	samples := int(durationSec * float64(sr))
	buf := bytes.NewBuffer(nil)

	// WAV 헤더 (44 bytes)
	binary.Write(buf, binary.LittleEndian, []byte("RIFF"))
	fileSize := 36 + samples*2
	binary.Write(buf, binary.LittleEndian, uint32(fileSize))
	binary.Write(buf, binary.LittleEndian, []byte("WAVE"))
	binary.Write(buf, binary.LittleEndian, []byte("fmt "))
	binary.Write(buf, binary.LittleEndian, uint32(16))
	binary.Write(buf, binary.LittleEndian, uint16(1))    // PCM
	binary.Write(buf, binary.LittleEndian, uint16(1))    // mono
	binary.Write(buf, binary.LittleEndian, uint32(sr))   // sr
	binary.Write(buf, binary.LittleEndian, uint32(sr*2)) // byte rate
	binary.Write(buf, binary.LittleEndian, uint16(2))    // block align
	binary.Write(buf, binary.LittleEndian, uint16(16))   // bits
	binary.Write(buf, binary.LittleEndian, []byte("data"))
	binary.Write(buf, binary.LittleEndian, uint32(samples*2))

	// 사인파 샘플
	for i := 0; i < samples; i++ {
		t := float64(i) / float64(sr)
		sample := int16(32000 * math.Sin(2*math.Pi*freqHz*t))
		binary.Write(buf, binary.LittleEndian, sample)
	}
	return buf.Bytes()
}

// ── STT 백그라운드 워커 (go-whisper contextPool 대응) ────────────

func sttWorker(id int) {
	fmt.Printf("[Worker-%d] STT 워커 시작\n", id)
	for job := range sttQueue {
		key := job.Topic + "::" + job.Filename
		statusMap.Store(key, "processing")

		var result STTResult
		var err error

		// 자동 재시도: 호스트마다 maxRetries회 — 모든 호스트 실패 시 처리대기
		maxAttempts := maxRetries * len(sttHosts)
		for attempt := 0; attempt < maxAttempts; attempt++ {
			host := hostForAttempt(attempt)
			result, err = transcribeBytesOnHost(job.WavBytes, host)
			if err == nil {
				break
			}
			if attempt < maxAttempts-1 {
				fmt.Printf("[Worker-%d] 재시도 %d/%d: %s host=%s (%v)\n",
					id, attempt+1, maxAttempts, job.Filename, host, err)
				if (attempt+1)%len(sttHosts) == 0 {
					time.Sleep(5 * time.Second) // 모든 호스트 한 라운드 후 대기
				}
			}
		}

		if err != nil {
			fmt.Printf("[Worker-%d] %d회 실패 → 처리대기: %s\n", id, maxRetries*len(sttHosts), job.Filename)
			statusMap.Store(key, "처리대기")
			continue
		}

		// 결과 보관 — saveMode에 따라 분기
		resultMapStore(key, result) // TTL 타임스탬프와 함께 저장

		// 개별 TXT 저장 (text/full 모드)
		if (saveMode == SaveModeText || saveMode == SaveModeFull) && result.Text != "" {
			txtPath := filepath.Join(recBase, job.Topic, strings.TrimSuffix(job.Filename, ".wav")+".txt")
			os.WriteFile(txtPath, []byte(result.Text), 0644)
		}

		// ── 화자 정렬 transcript.txt 재작성 ──────────────────────────
		// saveMode 무관하게 항상 실행. 파일명 시간 순 정렬 + 동일 화자 병합.
		speaker := result.Speaker
		if speaker == "" {
			speaker = "화자1"
		}

		// 트랜스크립트 모드: auto=자동 병합, manual=수동 병합
		mode := getTranscriptMode()
		if mode == TranscriptModeAuto {
			// ── 세그먼트별 화자 식별이 있으면 우선 사용 ──────────────────────
			if len(result.SpeakerSegments) > 0 {
				// 동일 화자 연속 텍스트 병합
				var grouped []TranscriptEntry
				timeStr := wavFilenameToTime(job.Filename)

				for _, seg := range result.SpeakerSegments {
					spk := seg.Speaker
					if spk == "" {
						spk = "화자1"
					}

					// ChunkBoundaryManager 미적용 (이미 세그먼트 단위로 완결)
					segText := seg.Text

					// 마지막 엔트리와 동일 화자면 텍스트 병합
					if len(grouped) > 0 && grouped[len(grouped)-1].Speaker == spk {
						grouped[len(grouped)-1].Text += " " + segText
					} else {
						grouped = append(grouped, TranscriptEntry{
							Filename: job.Filename,
							TimeStr:  timeStr,
							Speaker:  spk,
							Text:     segText,
							Source:   "whisper",
						})
					}
				}

				// 병합된 엔트리 기록
				for _, entry := range grouped {
					if entry.Text != "" {
						appendAndRewrite(job.Topic, entry)
					}
				}
			} else {
				// ── 폴백: 세그먼트별 화자 정보 없으면 기존 방식 ────────────────
				finalText := applyChunkBoundary(job.Topic, result.Text)
				if finalText != "" {
					appendAndRewrite(job.Topic, TranscriptEntry{
						Filename: job.Filename,
						TimeStr:  wavFilenameToTime(job.Filename),
						Speaker:  speaker,
						Text:     finalText,
						Source:   "whisper",
					})
				}
			}
		}

		// SRT 파일 (full 모드 한정)
		if saveMode == SaveModeFull && len(result.Segments) > 0 {
			srtPath := filepath.Join(recBase, job.Topic, strings.TrimSuffix(job.Filename, ".wav")+".srt")
			os.WriteFile(srtPath, []byte(buildSRT(result.Segments)), 0644)
		}

		// WAV 사후 처리 (full 모드 + WAV_CLEANUP 정책)
		applyWavCleanup(job.Topic, job.Filename)

		completedAt := time.Now().Format("15:04:05.000")
		statusMap.Store(key, "done")

		// metaMap에 CompletedAt 업데이트 (latency 측정용)
		if meta, ok := metaMap.Load(key); ok {
			info := meta.(RecordingInfo)
			info.CompletedAt = completedAt
			metaMap.Store(key, info)
		}

		// 표시용 텍스트 결정 (finalText는 세그먼트 처리 시 정의 안 될 수 있음)
		displayText := result.Text
		if len(result.SpeakerSegments) > 0 {
			// 세그먼트별 표시
			displayText = result.Text
		}
		preview := []rune(displayText)
		pv := string(preview)
		if len(preview) > 40 { pv = string(preview[:40]) + "..." }
		fmt.Printf("[Worker-%d] STT-OK [%s]: %s → %q\n", id, saveMode, job.Filename, pv)

		// /ws/live 브로드캐스트 — WsBroadcast 활성 시만 전송
		broadcastSpeaker := result.Speaker
		if broadcastSpeaker == "" {
			broadcastSpeaker = "화자1"
		}
		broadcastJSON(map[string]interface{}{
			"type":              "stt_result",
			"topic":             job.Topic,
			"filename":          job.Filename,
			"text":              result.Text,
			"segments":          result.Segments,
			"speaker_segments":  result.SpeakerSegments, // ← 추가: 세그먼트별 화자
			"speaker":           broadcastSpeaker,
			"timestamp":         time.Now().UnixMilli(), // 텍스트 변환 완료 시간 (ms)
			"complete_at":       time.Now().Format("15:04:05.000"),
		})
	}
}

// ── ChunkBoundaryManager ─────────────────────────────────────
// 청크 간 문장 경계 복원: 이전 청크의 미완성 문장을 현재 텍스트 앞에 붙여 처리.
// 완결된 문장만 transcript에 기록, 미완성 꼬리는 다음 청크로 넘김.

// isKoreanComplete: 한국어 문장 완결 여부 (종결 어미/부호 기준)
func isKoreanComplete(text string) bool {
	complete := []string{
		"다.", "요.", "까?", "까요?", "네.", "죠.", "죠?",
		"습니다.", "겠습니다.", "겠어요.", "었어요.", "했어요.",
		"입니다.", "합니다.", "됩니다.",
		"!", "?",
	}
	t := strings.TrimSpace(text)
	for _, end := range complete {
		if strings.HasSuffix(t, end) {
			return true
		}
	}
	return false
}

// splitKoreanSentences: 한국어 문장 경계 분리
// 종결부호 뒤 공백을 기준으로 분리, 빈 항목 제거.
func splitKoreanSentences(text string) []string {
	// 종결 패턴: 다/요/습니다/겠습니다 + 마침표, 또는 ?/!  뒤 공백
	var result []string
	runes  := []rune(text)
	start  := 0
	n      := len(runes)

	for i := 0; i < n; i++ {
		ch := runes[i]
		// 마침표·!·? 뒤에 공백이 있으면 경계
		if (ch == '.' || ch == '!' || ch == '?') && i+1 < n && runes[i+1] == ' ' {
			sentence := strings.TrimSpace(string(runes[start : i+1]))
			if sentence != "" {
				result = append(result, sentence)
			}
			start = i + 2 // 공백 다음부터 새 문장
			i++
		}
	}
	// 나머지 (미완성 가능)
	if tail := strings.TrimSpace(string(runes[start:])); tail != "" {
		result = append(result, tail)
	}
	return result
}

// timeStrClose: "HH:MM:SS" 두 값이 maxSec 초 이내인지 확인
func timeStrClose(a, b string, maxSec int) bool {
	parse := func(s string) int {
		var h, m, sec int
		fmt.Sscanf(s, "%d:%d:%d", &h, &m, &sec)
		return h*3600 + m*60 + sec
	}
	diff := parse(a) - parse(b)
	if diff < 0 { diff = -diff }
	return diff <= maxSec
}

// applyChunkBoundary: pending + rawText 합치기 → 완결 문장 반환 + 새 pending 저장
func applyChunkBoundary(topic, rawText string) string {
	topicPendingMu.Lock()
	pending := topicPending[topic]
	topicPendingMu.Unlock()

	combined := strings.TrimSpace(pending + " " + rawText)
	if combined == "" {
		return ""
	}

	sentences := splitKoreanSentences(combined)
	if len(sentences) == 0 {
		return ""
	}

	last := sentences[len(sentences)-1]
	var newPending string
	var completed []string

	if !isKoreanComplete(last) {
		// 마지막 조각이 미완성 → pending으로 보류
		newPending = last
		completed  = sentences[:len(sentences)-1]
	} else {
		completed = sentences
	}

	topicPendingMu.Lock()
	topicPending[topic] = newPending
	topicPendingMu.Unlock()

	return strings.TrimSpace(strings.Join(completed, " "))
}

// clearPending: 녹음 종료 시 남은 pending을 강제 플러시
func flushPending(topic string) string {
	topicPendingMu.Lock()
	remaining := strings.TrimSpace(topicPending[topic])
	topicPending[topic] = ""
	topicPendingMu.Unlock()
	return remaining
}

// wavFilenameToTime: "rec_150405_000.wav" → "15:04:05"
func wavFilenameToTime(filename string) string {
	base  := strings.TrimSuffix(filename, ".wav")
	parts := strings.Split(base, "_")
	if len(parts) >= 2 && len(parts[1]) >= 6 {
		t := parts[1]
		return t[0:2] + ":" + t[2:4] + ":" + t[4:6]
	}
	return time.Now().Format("15:04:05")
}

// appendAndRewrite: 엔트리 추가 후 파일명(시간) 순 정렬, 동일 화자 연속 발화 병합,
// Markdown 형식으로 transcript.txt 전체 재작성.
// 동시 호출 안전 (topicEntriesMu 로 보호).
func appendAndRewrite(topic string, entry TranscriptEntry) {
	topicEntriesMu.Lock()
	defer topicEntriesMu.Unlock()

	existing := topicEntries[topic]

	if entry.Source == "whisper" && entry.TimeStr != "" {
		// Whisper 결과 도착 시: 동일 시간대(±30초)의 browser 임시 항목 제거
		filtered := existing[:0]
		for _, e := range existing {
			if e.Source == "browser" && timeStrClose(e.TimeStr, entry.TimeStr, 30) {
				continue // browser 임시 항목 제거
			}
			filtered = append(filtered, e)
		}
		existing = filtered
	}

	topicEntries[topic] = append(existing, entry)
	entries := topicEntries[topic]

	// 파일명 오름차순 = 시간 순
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Filename < entries[j].Filename
	})

	// 연속된 동일 화자 발화 병합
	type group struct {
		speaker string
		timeStr string
		texts   []string
	}
	var groups []group
	for _, e := range entries {
		t := e.Text
		if t == "" {
			t = "(인식된 내용 없음)"
		}
		if len(groups) > 0 && groups[len(groups)-1].speaker == e.Speaker {
			groups[len(groups)-1].texts = append(groups[len(groups)-1].texts, t)
		} else {
			groups = append(groups, group{
				speaker: e.Speaker,
				timeStr: e.TimeStr,
				texts:   []string{t},
			})
		}
	}

	var sb strings.Builder
	sb.WriteString("# 회의 전사 기록\n\n")
	for _, g := range groups {
		fmt.Fprintf(&sb, "**[%s] %s**\n%s\n\n",
			g.timeStr, g.speaker, strings.Join(g.texts, " "))
	}

	topicDir := filepath.Join(recBase, topic)
	os.MkdirAll(topicDir, 0755)
	os.WriteFile(filepath.Join(topicDir, "transcript.txt"), []byte(sb.String()), 0644)
}

// ── /api/recordings/start ─────────────────────────────────────
// POST ?topic=xxx → 녹음 폴더 생성 (녹음 시작 시 호출)

func handleRecordingStart(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" { return }
	if r.Method != "POST" {
		http.Error(w, "POST only", 405)
		return
	}
	topic := sanitizeName(r.URL.Query().Get("topic"))
	if topic == "" {
		http.Error(w, "topic required", 400)
		return
	}
	dir := filepath.Join(recBase, topic)
	if err := os.MkdirAll(dir, 0755); err != nil {
		http.Error(w, "폴더 생성 실패: "+err.Error(), 500)
		return
	}

	// 새 녹음 세션 시작 — 이전 pending/entries 초기화
	topicPendingMu.Lock()
	topicPending[topic] = ""
	topicPendingMu.Unlock()
	topicEntriesMu.Lock()
	topicEntries[topic] = nil
	topicEntriesMu.Unlock()

	fmt.Printf("[start] 녹음 폴더 생성: %s\n", dir)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"topic": topic,
		"dir":   dir,
	})
}

// ── /api/recordings/stop ─────────────────────────────────────
// POST ?topic=xxx → 녹음 세션 종료: pending 버퍼 강제 플러시 후 transcript 갱신

func handleRecordingStop(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" {
		return
	}
	if r.Method != "POST" {
		http.Error(w, "POST only", 405)
		return
	}
	topic := sanitizeName(r.URL.Query().Get("topic"))
	if topic == "" {
		http.Error(w, "topic required", 400)
		return
	}

	// ChunkBoundaryManager: 남은 미완성 문장 강제 기록
	if remaining := flushPending(topic); remaining != "" {
		appendAndRewrite(topic, TranscriptEntry{
			Filename: "final_" + time.Now().Format("150405") + ".wav",
			TimeStr:  time.Now().Format("15:04:05"),
			Speaker:  "화자1",
			Text:     remaining,
		})
		fmt.Printf("[stop] pending flush [%s]: %q\n", topic, remaining)
	}

	fmt.Printf("[stop] 녹음 종료: %s\n", topic)

	// ── [신규] AUTO_SUMMARY: 자동 요약 트리거 ────────────────────
	if autoSummaryEnabled && saveMode != SaveModeMemory {
		txPath := filepath.Join(recBase, topic, "transcript.txt")
		if _, err := os.Stat(txPath); err == nil {
			// 이미 실행 중이면 스킵
			alreadyRunning := false
			if v, ok := pipelineMap.Load(topic); ok {
				st := v.(PipelineState)
				if st.Status == PipelineRunning || st.Status == PipelineSummarizing || st.Status == PipelineGenerating {
					alreadyRunning = true
				}
			}
			if !alreadyRunning {
				doctype := getSummaryDoctype()
				state := PipelineState{Status: PipelineRunning, Step: "starting", Message: "자동 요약 시작..."}
				pipelineMap.Store(topic, state)
				broadcastJSON(map[string]interface{}{"type": "pipeline_progress", "topic": topic, "state": state})
				go runPostPipeline(topic, txPath, doctype)
				fmt.Printf("[stop] 자동 요약 시작: %s (doctype=%s)\n", topic, doctype)
			}
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"topic": topic, "status": "stopped"})
}

// ── 파이프라인 API ────────────────────────────────────────────

// POST /api/summary?topic=xxx&doctype=docx  — 요약+문서 생성 트리거
func handleSummaryStart(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" { return }
	if r.Method != "POST" { http.Error(w, "POST only", 405); return }

	topic := sanitizeName(r.URL.Query().Get("topic"))
	doctype := r.URL.Query().Get("doctype")
	if topic == "" { http.Error(w, "topic required", 400); return }
	if doctype == "" { doctype = "docx" }

	// 이미 실행 중이면 거부
	if v, ok := pipelineMap.Load(topic); ok {
		st := v.(PipelineState)
		if st.Status == PipelineRunning || st.Status == PipelineSummarizing || st.Status == PipelineGenerating {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(st)
			return
		}
	}

	txPath := filepath.Join(recBase, topic, "transcript.txt")
	if _, err := os.Stat(txPath); err != nil {
		http.Error(w, "transcript.txt not found — 녹음 후 시도해주세요", 404)
		return
	}

	state := PipelineState{Status: PipelineRunning, Step: "starting", Message: "파이프라인 시작..."}
	pipelineMap.Store(topic, state)
	broadcastJSON(map[string]interface{}{"type": "pipeline_progress", "topic": topic, "state": state})

	go runPostPipeline(topic, txPath, doctype)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "started", "topic": topic, "doctype": doctype})
}

// GET /api/summary/status?topic=xxx  — 파이프라인 현재 상태
func handleSummaryStatus(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	topic := sanitizeName(r.URL.Query().Get("topic"))
	if topic == "" { http.Error(w, "topic required", 400); return }

	if v, ok := pipelineMap.Load(topic); ok {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(v.(PipelineState))
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(PipelineState{Status: PipelineIdle})
}

// GET /api/docs/download?topic=xxx&file=xxx.docx  — 생성 문서 다운로드
func handleDocDownload(w http.ResponseWriter, r *http.Request) {
	topic := sanitizeName(r.URL.Query().Get("topic"))
	file  := filepath.Base(r.URL.Query().Get("file")) // path traversal 방지
	if topic == "" || file == "" { http.Error(w, "topic and file required", 400); return }

	fpath := filepath.Join(recBase, topic, file)
	if _, err := os.Stat(fpath); err != nil {
		// summary.md 도 허용
		fpath2 := filepath.Join(recBase, topic, "summary.md")
		if file == "summary.md" {
			if _, e2 := os.Stat(fpath2); e2 == nil { fpath = fpath2 } else {
				http.Error(w, "file not found", 404); return
			}
		} else {
			http.Error(w, "file not found", 404); return
		}
	}

	w.Header().Set("Content-Disposition", "attachment; filename=\""+file+"\"")
	http.ServeFile(w, r, fpath)
}

// GET /api/docs/view?topic=xxx  — summary.md 내용 반환 (UI 미리보기)
func handleDocView(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	topic := sanitizeName(r.URL.Query().Get("topic"))
	if topic == "" { http.Error(w, "topic required", 400); return }

	sumPath := filepath.Join(recBase, topic, "summary.md")
	data, err := os.ReadFile(sumPath)
	if err != nil {
		http.Error(w, "summary.md not found", 404); return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.Write(data)
}

// runPostPipeline: Python post_pipeline.py subprocess 실행 + WS 브로드캐스트
func runPostPipeline(topic, txPath, doctype string) {
	outDir := filepath.Join(recBase, topic)

	pyCmd := exec.Command("python", "pipeline/post_pipeline.py",
		"--transcript", txPath,
		"--topic", topic,
		"--doctype", doctype,
		"--outdir", outDir,
	)
	pyCmd.Dir = "."
	stdoutPipe, err := pyCmd.StdoutPipe()
	if err != nil {
		setFailed(topic, "subprocess stdout pipe 실패: "+err.Error())
		return
	}
	pyCmd.Stderr = os.Stderr

	if err := pyCmd.Start(); err != nil {
		setFailed(topic, "subprocess 시작 실패: "+err.Error())
		return
	}

	// JSON 줄 파싱 + WS 브로드캐스트
	scanner := bufio.NewScanner(stdoutPipe)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" { continue }
		var ev map[string]interface{}
		if err := json.Unmarshal([]byte(line), &ev); err != nil {
			continue
		}

		event, _ := ev["event"].(string)
		state := PipelineState{}

		switch event {
		case "progress":
			step, _ := ev["step"].(string)
			msg,  _ := ev["message"].(string)
			sumP, _ := ev["sum_path"].(string)
			switch step {
			case "summarizing":
				state = PipelineState{Status: PipelineSummarizing, Step: step, Message: msg, SumPath: sumP}
			case "generating":
				state = PipelineState{Status: PipelineGenerating, Step: step, Message: msg, SumPath: sumP}
			default:
				state = PipelineState{Status: PipelineRunning, Step: step, Message: msg}
			}
		case "done":
			sumP, _ := ev["sum_path"].(string)
			docP, _ := ev["doc_path"].(string)
			msg,  _ := ev["message"].(string)
			elapsed, _ := ev["elapsed"].(float64)
			docFile := filepath.Base(docP)
			state = PipelineState{
				Status: PipelineDone, Step: "done", Message: msg,
				SumPath: sumP, DocPath: docP, DocFile: docFile, Elapsed: elapsed,
			}
		case "error":
			msg, _ := ev["message"].(string)
			state = PipelineState{Status: PipelineError, Step: "error", Message: msg, Error: msg}
		default:
			continue
		}

		pipelineMap.Store(topic, state)
		broadcastJSON(map[string]interface{}{"type": "pipeline_progress", "topic": topic, "state": state})
		fmt.Printf("[pipeline] topic=%s event=%s msg=%s\n", topic, event, state.Message)
	}

	pyCmd.Wait()

	// 최종 상태가 done/error가 아니면 error 처리
	if v, ok := pipelineMap.Load(topic); ok {
		st := v.(PipelineState)
		if st.Status != PipelineDone && st.Status != PipelineError {
			setFailed(topic, "파이프라인이 비정상 종료됨")
		}
	}
}

func setFailed(topic, msg string) {
	state := PipelineState{Status: PipelineError, Step: "error", Error: msg, Message: msg}
	pipelineMap.Store(topic, state)
	broadcastJSON(map[string]interface{}{"type": "pipeline_progress", "topic": topic, "state": state})
	fmt.Printf("[pipeline] ERROR topic=%s: %s\n", topic, msg)
}

// SRT 생성 (go-whisper WriteSRT 대응)
func buildSRT(segs []STTSegment) string {
	var sb strings.Builder
	for i, s := range segs {
		fmt.Fprintf(&sb, "%d\n%s --> %s\n%s\n\n",
			i+1, srtTime(s.Start), srtTime(s.End), strings.TrimSpace(s.Text))
	}
	return sb.String()
}

func srtTime(sec float64) string {
	h  := int(sec) / 3600
	m  := (int(sec) % 3600) / 60
	s  := int(sec) % 60
	ms := int((sec-float64(int(sec)))*1000)
	return fmt.Sprintf("%02d:%02d:%02d,%03d", h, m, s, ms)
}

// WAV 파일 → Python STT (라운드로빈) → STTResult (text + segments)
// go-whisper contextPool 라운드로빈 대응
// transcribeBytes: WAV 바이트를 메모리에서 직접 STT 처리 (파일 저장 없음)
func transcribeBytes(data []byte) (STTResult, error) {
	return transcribeBytesOnHost(data, nextSTTHost())
}

func transcribeBytesOnHost(data []byte, host string) (STTResult, error) {
	empty := STTResult{}

	if len(data) < 44 {
		return empty, fmt.Errorf("too short")
	}
	conn, _, err := websocket.DefaultDialer.Dial(host, nil)
	if err != nil {
		return empty, fmt.Errorf("STT 연결 실패 (%s): %v", host, err)
	}
	defer conn.Close()

	// config — speaker_id 모드 + 현재 시나리오 전달
	cfgMsg, _ := json.Marshal(map[string]string{
		"type":     "config",
		"mode":     "speaker_id",
		"language": "ko",
		"scenario": getScenario(),
	})
	if err := conn.WriteMessage(websocket.TextMessage, cfgMsg); err != nil {
		return empty, err
	}

	// ready 대기
	conn.SetReadDeadline(time.Now().Add(15 * time.Second))
	for {
		_, msg, err := conn.ReadMessage()
		if err != nil { return empty, err }
		var d map[string]interface{}
		json.Unmarshal(msg, &d)
		if d["type"] == "ready" { break }
	}

	// WAV 전송
	if err := conn.WriteMessage(websocket.BinaryMessage, data); err != nil {
		return empty, err
	}

	// 결과 대기 (파일 길이 × 5 + 60초)
	estSec := float64(len(data)) / float64(16000*2)
	// CPU 환경에서 large-v3-turbo는 실시간의 20~60배 소요 가능
	// estSec*60 + 120 으로 넉넉하게 설정 (GPU 환경에선 거의 즉시 완료)
	timeout := time.Duration(estSec*60+120) * time.Second
	conn.SetReadDeadline(time.Now().Add(timeout))

	for {
		_, msg, err := conn.ReadMessage()
		if err != nil { return empty, err }

		var d map[string]json.RawMessage
		if err := json.Unmarshal(msg, &d); err != nil { continue }

		var msgType string
		json.Unmarshal(d["type"], &msgType)

		switch msgType {
		case "result":
			var res STTResult
			json.Unmarshal(msg, &res)
			return res, nil
		case "error":
			var errMsg string
			json.Unmarshal(d["message"], &errMsg)
			return empty, fmt.Errorf("STT: %s", errMsg)
		}
	}
}

// ── Phase-1 Headless API 헬퍼 ────────────────────────────────

// authMiddleware: API_KEY 환경변수 설정 시 X-API-Key 헤더 또는 ?api_key= 검증
func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		setCORS(w)
		if r.Method == "OPTIONS" { return }
		if !monitor.AuthRequired() { next(w, r); return }

		key := r.Header.Get("X-API-Key")
		if key == "" { key = r.URL.Query().Get("api_key") }
		if !monitor.ValidKey(key) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(401)
			fmt.Fprintf(w, `{"error":"unauthorized","hint":"X-API-Key header or ?api_key= required"}`)
			return
		}
		next(w, r)
	}
}

// handleDirectSTT: POST /api/stt — WAV 바이너리 직접 업로드 → STT 결과 반환
// 외부 API 클라이언트용. 브라우저 없이 WAV 파일을 바로 인식.
// Content-Type: audio/wav 또는 application/octet-stream
// Query: topic (선택), scenario (선택)
func handleDirectSTT(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" { return }
	if r.Method != "POST" { http.Error(w, `{"error":"POST only"}`, 405); return }

	r.Body = http.MaxBytesReader(w, r.Body, 50<<20) // 50 MB 제한
	data, err := io.ReadAll(r.Body)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		http.Error(w, `{"error":"read failed"}`, 400)
		return
	}
	if len(data) < 44 {
		w.Header().Set("Content-Type", "application/json")
		http.Error(w, `{"error":"invalid WAV: too short"}`, 400)
		return
	}

	// 시나리오 쿼리 파라미터 → 전역 시나리오 임시 변경 (요청 스코프 아님 — 로그만)
	scenario := r.URL.Query().Get("scenario")
	if scenario == "" { scenario = getScenario() }

	host := nextSTTHost()
	result, err := transcribeBytesOnHost(data, host)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(502)
		fmt.Fprintf(w, `{"error":%q,"host":%q}`, err.Error(), host)
		return
	}

	topic := sanitizeName(r.URL.Query().Get("topic"))

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"text":     result.Text,
		"speaker":  result.Speaker,
		"segments": result.Segments,
		"topic":    topic,
		"scenario": scenario,
		"host":     host,
	})
}

// handleSpeechText: POST /api/speech-text
// 브라우저 Web Speech API 결과를 즉시 transcript.txt에 기록 (< 100ms).
// Whisper가 나중에 같은 시간대 항목을 교체하여 정확도 교정.
//
// Body (JSON): {"topic":"회의","text":"안녕하세요","speaker":"화자1","time":"14:30:00"}
func handleSpeechText(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"POST required"}`, http.StatusMethodNotAllowed)
		return
	}
	var body struct {
		Topic   string `json:"topic"`
		Text    string `json:"text"`
		Speaker string `json:"speaker"`
		Time    string `json:"time"` // "HH:MM:SS"
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Topic == "" || body.Text == "" {
		http.Error(w, `{"error":"topic and text required"}`, http.StatusBadRequest)
		return
	}
	if body.Speaker == "" {
		body.Speaker = "화자1"
	}
	if body.Time == "" {
		body.Time = time.Now().Format("15:04:05")
	}

	// 즉시 transcript.txt 기록 (Source="browser" → Whisper 도착 시 교체됨)
	appendAndRewrite(body.Topic, TranscriptEntry{
		Filename: "wsa_" + strings.ReplaceAll(body.Time, ":", "") + "_000.wav",
		TimeStr:  body.Time,
		Speaker:  body.Speaker,
		Text:     body.Text,
		Source:   "browser",
	})

	// /ws/live 브로드캐스트 (WS 구독자에게 즉시 알림)
	broadcastJSON(map[string]interface{}{
		"type":    "stt_result",
		"topic":   body.Topic,
		"text":    body.Text,
		"speaker": body.Speaker,
		"source":  "browser",
	})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "time": body.Time})
}

// handleMonitorConfig: GET/POST /api/monitor/config — 런타임 모드 조회/변경
func handleMonitorConfig(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" { return }

	if r.Method == "GET" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(monitor.Get())
		return
	}

	if r.Method == "POST" {
		// JSON 파싱 — 포인터로 받아 "명시적으로 보낸 필드만" 변경
		var body struct {
			Headless      *bool   `json:"headless"`
			WsBroadcast   *bool   `json:"ws_broadcast"`
			SaveMode      *string `json:"save_mode"`
			WavCleanup    *string `json:"wav_cleanup"`
			TranscriptMode *string `json:"transcript_mode"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, `{"error":"invalid JSON"}`, 400)
			return
		}
		monitor.Set(body.Headless, body.WsBroadcast)

		if body.SaveMode != nil {
			switch strings.ToLower(*body.SaveMode) {
			case "memory": saveMode = SaveModeMemory
			case "text":   saveMode = SaveModeText
			case "full":   saveMode = SaveModeFull
			default:
				http.Error(w, `{"error":"invalid save_mode (memory|text|full)"}`, 400)
				return
			}
			fmt.Printf("[monitor] save_mode → %s\n", saveMode)
		}
		if body.WavCleanup != nil {
			switch strings.ToLower(*body.WavCleanup) {
			case "keep":   setWavCleanup(WavCleanupKeep)
			case "delete": setWavCleanup(WavCleanupDelete)
			case "backup": setWavCleanup(WavCleanupBackup)
			default:
				http.Error(w, `{"error":"invalid wav_cleanup (keep|delete|backup)"}`, 400)
				return
			}
			fmt.Printf("[monitor] wav_cleanup → %s\n", getWavCleanup())
		}
		if body.TranscriptMode != nil {
			switch strings.ToLower(*body.TranscriptMode) {
			case "auto":   setTranscriptMode(TranscriptModeAuto)
			case "manual": setTranscriptMode(TranscriptModeManual)
			default:
				http.Error(w, `{"error":"invalid transcript_mode (auto|manual)"}`, 400)
				return
			}
			fmt.Printf("[monitor] transcript_mode → %s\n", getTranscriptMode())
		}
		fmt.Printf("[monitor] config 변경: headless=%v ws_broadcast=%v save_mode=%s wav_cleanup=%s transcript_mode=%s\n",
			monitor.Headless, monitor.WsBroadcast, saveMode, getWavCleanup(), getTranscriptMode())

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(monitor.Get())
		return
	}

	http.Error(w, "GET or POST only", 405)
}

// ── main ──────────────────────────────────────────────────────

func main() {
	port := "8090"
	if len(os.Args) > 1 {
		port = os.Args[1]
	}

	os.MkdirAll(recBase, 0755)

	mux := http.NewServeMux()

	// 녹음 파일 API
	mux.HandleFunc("/api/config",            handleConfig)          // GET 클라이언트 설정
	mux.HandleFunc("/api/mode",              handleMode)            // GET/POST 저장 모드 조회/변경
	mux.HandleFunc("/api/scenario",          handleScenario)        // GET/POST STT 시나리오
	mux.HandleFunc("/api/recordings/start",  handleRecordingStart)  // POST 폴더 생성
	mux.HandleFunc("/api/recordings/stop",   handleRecordingStop)   // POST 녹음 종료 + pending 플러시
	mux.HandleFunc("/api/recordings",        handleRecordings)      // POST/GET
	mux.HandleFunc("/api/text",         handleText)         // GET text content
	mux.HandleFunc("/api/retranscribe", handleRetranscribe) // POST retry
	mux.HandleFunc("/api/hwinfo",       handleHWInfo)       // GET 하드웨어 프로파일

	// 저장소 관리 API
	mux.HandleFunc("/api/storage/stats",  handleStorageStats)  // GET 전체 통계
	mux.HandleFunc("/api/storage/topics", handleStorageTopics) // GET 주제 목록
	mux.HandleFunc("/api/storage/detail", handleStorageDetail) // GET 주제별 파일 상세
	mux.HandleFunc("/api/storage/delete", handleStorageDelete)       // DELETE 파일/주제 삭제
	mux.HandleFunc("/api/storage/delete-all", handleStorageDeleteAll) // DELETE 전체 recordings 삭제 (confirm=yes 필수)

	// 트랜스크립트 병합 API
	mux.HandleFunc("/api/transcript/merge", handleTranscriptMerge) // POST 수동 모드: 텍스트 파일 병합

	// 파이프라인 API (요약 + 문서 생성)
	mux.HandleFunc("/api/summary",        handleSummaryStart)  // POST 요약 트리거
	mux.HandleFunc("/api/summary/status", handleSummaryStatus) // GET 상태 조회
	mux.HandleFunc("/api/docs/download",  handleDocDownload)   // GET 문서 다운로드
	mux.HandleFunc("/api/docs/view",      handleDocView)       // GET summary.md 미리보기

	// Legacy API (호환 유지)
	mux.HandleFunc("/api/save",        handleSave)
	mux.HandleFunc("/api/transcripts", handleTranscripts)

	// Phase-1: Headless / Monitor API
	mux.HandleFunc("/api/stt",            authMiddleware(handleDirectSTT))    // POST WAV → STT 즉시 반환
	mux.HandleFunc("/api/speech-text",    handleSpeechText)                   // POST 브라우저 STT 즉시 기록
	mux.HandleFunc("/api/monitor/config", authMiddleware(handleMonitorConfig)) // GET/POST 런타임 설정

	// WebSocket
	mux.HandleFunc("/ws/stt",  proxySTT)     // STT 프록시
	mux.HandleFunc("/ws/live", handleLiveWS) // 실시간 결과 푸시

	// Static files — HEADLESS=1 이면 UI 서빙 비활성
	if monitor.Headless {
		mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			if r.URL.Path == "/" {
				json.NewEncoder(w).Encode(map[string]string{
					"mode":    "headless",
					"version": "voice-pipeline/1.0",
					"docs":    "POST /api/stt | /api/recordings/* | /api/summary | /api/monitor/config",
				})
			} else {
				w.WriteHeader(404)
				fmt.Fprintf(w, `{"error":"not_found","path":%q,"hint":"UI disabled in headless mode"}`, r.URL.Path)
			}
		})
	} else {
		mux.Handle("/", http.FileServer(http.Dir(".")))
	}

	// 시작 로그
	fmt.Printf("Voice Server → http://localhost:%s\n", port)
	fmt.Printf("   모드      : %s\n", map[bool]string{true: "HEADLESS (API 전용)", false: "UI + API"}[monitor.Headless])
	fmt.Printf("   저장 모드  : SAVE_MODE=%s\n", saveMode)
	fmt.Printf("   WS 브로드캐스트: %v\n", monitor.WsBroadcast)
	if monitor.AuthRequired() {
		fmt.Printf("   인증       : API_KEY 설정됨 (X-API-Key 헤더 필요)\n")
	} else {
		fmt.Printf("   인증       : 없음 (API_KEY 미설정)\n")
	}
	fmt.Printf("   설정: maxFileMB=%.1f  silenceDuration=%dms  threshold=%.3f  minSpeech=%dms\n",
		clientCfg.MaxFileMB, clientCfg.SilenceDurationMs, clientCfg.SilenceThreshold, clientCfg.MinSpeechMs)

	if err := http.ListenAndServe(":"+port, mux); err != nil {
		fmt.Fprintf(os.Stderr, "오류: %v\n", err)
		os.Exit(1)
	}
}

// ── /api/config ───────────────────────────────────────────────
// GET → 클라이언트가 VoiceSTT.init()에 사용할 설정 반환 (saveMode 포함)

func handleConfig(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"maxFileMB":        clientCfg.MaxFileMB,
		"silenceDuration":  clientCfg.SilenceDurationMs,
		"silenceThreshold": clientCfg.SilenceThreshold,
		"minSpeechMs":      clientCfg.MinSpeechMs,
		"saveMode":         string(saveMode),
		"scenario":         getScenario(),
	})
}

// ── /api/scenario ─────────────────────────────────────────────
// GET  → 현재 시나리오 + 전체 목록 조회
// POST → 시나리오 변경 (재시작 없이 런타임 전환)
//   body: {"scenario": "quiet"} | {"scenario": "noisy"} | ...

func handleScenario(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	w.Header().Set("Content-Type", "application/json")
	if r.Method == "OPTIONS" {
		return
	}

	type ScenarioMeta struct {
		Name        string `json:"name"`
		Label       string `json:"label"`
		Description string `json:"desc"`
	}
	options := []ScenarioMeta{
		{"quiet",     "조용한 회의실",  "beam=5, no_speech=0.40"},
		{"noisy",     "시끄러운 환경",  "beam=3, no_speech=0.50"},
		{"interview", "1:1 인터뷰",    "beam=5, no_speech=0.38"},
		{"debate",    "다자 토론",     "beam=3, no_speech=0.50"},
		{"phone",     "전화 녹음",     "beam=3, no_speech=0.55"},
	}

	if r.Method == "GET" {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"scenario": getScenario(),
			"options":  options,
		})
		return
	}

	if r.Method == "POST" {
		var req struct {
			Scenario string `json:"scenario"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid JSON", 400)
			return
		}
		if !setScenario(req.Scenario) {
			http.Error(w, "invalid scenario: "+req.Scenario, 400)
			return
		}
		fmt.Printf("[scenario] 시나리오 변경: %s\n", req.Scenario)
		json.NewEncoder(w).Encode(map[string]string{"scenario": req.Scenario})
	}
}

// ── /api/mode ─────────────────────────────────────────────────
// GET  → 현재 저장 모드 조회
// POST → 저장 모드 변경 (재시작 없이 런타임 전환)
//   body: {"mode": "memory"} | {"mode": "text"} | {"mode": "full"}

func handleMode(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	w.Header().Set("Content-Type", "application/json")

	if r.Method == "OPTIONS" {
		return
	}

	if r.Method == "GET" {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"saveMode":    string(saveMode),
			"description": saveModeDescription(saveMode),
			"options": []map[string]string{
				{"mode": "memory", "label": "A안: 메모리 전용 (파일 없음)"},
				{"mode": "text",   "label": "B안: TXT만 저장 (WAV 없음)"},
				{"mode": "full",   "label": "전체 저장 (WAV+TXT+SRT)"},
			},
		})
		return
	}

	if r.Method == "POST" {
		var req struct {
			Mode string `json:"mode"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid json", 400)
			return
		}
		prev := saveMode
		switch strings.ToLower(req.Mode) {
		case "memory":
			saveMode = SaveModeMemory
		case "text":
			saveMode = SaveModeText
			os.MkdirAll(recBase, 0755)
		case "full":
			saveMode = SaveModeFull
			os.MkdirAll(recBase, 0755)
		default:
			http.Error(w, "invalid mode: memory | text | full", 400)
			return
		}
		fmt.Printf("[mode] 저장 모드 변경: %s → %s\n", prev, saveMode)
		json.NewEncoder(w).Encode(map[string]string{
			"prev":    string(prev),
			"current": string(saveMode),
			"desc":    saveModeDescription(saveMode),
		})
		return
	}

	http.Error(w, "GET or POST only", 405)
}

func saveModeDescription(m SaveMode) string {
	switch m {
	case SaveModeMemory:
		return "A안: WAV/TXT 파일 없음, 메모리에만 보관 (서버 재시작 시 초기화)"
	case SaveModeText:
		return "B안: WAV 없음, TXT만 저장 — 재시작 후에도 텍스트 유지, 파이프라인 연동 가능"
	case SaveModeFull:
		return "전체 저장: WAV+TXT+SRT 모두 저장, 재처리(retranscribe) 가능"
	default:
		return ""
	}
}

// ── /api/recordings ───────────────────────────────────────────
// POST ?topic=xxx  body=WAV bytes  → 파일 저장 + STT 큐 자동 등록
// GET  ?topic=xxx                  → 파일 목록 + 상태 반환

func handleRecordings(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" {
		return
	}

	topic := sanitizeName(r.URL.Query().Get("topic"))
	if topic == "" {
		topic = "default"
	}

	if r.Method == "POST" {
		body, err := io.ReadAll(io.LimitReader(r.Body, 35*1024*1024))
		if err != nil || len(body) < 44 {
			http.Error(w, "invalid audio", 400)
			return
		}

		// 타임스탬프 기반 고유 ID (파일명 형식 유지, 실제 파일은 저장 안 함)
		filename := fmt.Sprintf("rec_%s.wav", time.Now().Format("150405_000"))
		key := topic + "::" + filename
		for {
			if _, exists := statusMap.Load(key); !exists {
				break
			}
			time.Sleep(time.Millisecond)
			filename = fmt.Sprintf("rec_%s.wav", time.Now().Format("150405_000"))
			key = topic + "::" + filename
		}

		sizeKB := math.Round(float64(len(body))/1024.0*10) / 10

		// WAV 파일 저장 (full 모드에서만)
		topicDir := filepath.Join(recBase, topic)
		os.MkdirAll(topicDir, 0755) // 혹시 미생성 시 보완
		if saveMode == SaveModeFull {
			wavPath := filepath.Join(topicDir, filename)
			if err := os.WriteFile(wavPath, body, 0644); err != nil {
				fmt.Printf("[recordings] WAV 저장 실패 (%s): %v\n", filename, err)
			}
		}

		statusMap.Store(key, "queued")
		metaMap.Store(key, RecordingInfo{
			Filename: filename,
			Created:  time.Now().Format("15:04:05"),
			SizeKB:   sizeKB,
			Status:   "queued",
		})

		select {
		case sttQueue <- STTJob{topic, filename, body}: // 바이트 직접 전달 (파일 재접근 없음)
		default:
			statusMap.Store(key, "처리대기")
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"filename": filename,
			"sizeKB":   sizeKB,
			"status":   "queued",
		})
		return
	}

	// GET: 목록 — 메모리 + 파일(text/full 모드) 합산
	seen := map[string]bool{}
	var list []RecordingInfo
	prefix := topic + "::"

	// 1. 메모리 목록 (현재 세션 처리 결과)
	metaMap.Range(func(k, v interface{}) bool {
		key := k.(string)
		if !strings.HasPrefix(key, prefix) {
			return true
		}
		rec := v.(RecordingInfo)
		if st, ok := statusMap.Load(key); ok {
			rec.Status = st.(string)
		}
		if _, ok := resultMapLoad(key); ok {
			rec.HasText = true
		}
		list = append(list, rec)
		seen[rec.Filename] = true
		return true
	})

	// 2. 디스크 파일 목록 (text/full 모드: 서버 재시작 후 이전 결과 포함)
	if saveMode == SaveModeText || saveMode == SaveModeFull {
		topicDir := filepath.Join(recBase, topic)
		entries, _ := os.ReadDir(topicDir)
		for _, e := range entries {
			name := e.Name()
			// text 모드: .txt 기준 / full 모드: .wav 기준
			var wavName string
			if saveMode == SaveModeText && strings.HasSuffix(name, ".txt") {
				wavName = strings.TrimSuffix(name, ".txt") + ".wav"
			} else if saveMode == SaveModeFull && strings.HasSuffix(name, ".wav") {
				wavName = name
			} else {
				continue
			}
			if seen[wavName] {
				continue // 이미 메모리에 있음
			}
			info, _ := e.Info()
			txtPath := filepath.Join(topicDir, strings.TrimSuffix(wavName, ".wav")+".txt")
			srtPath := filepath.Join(topicDir, strings.TrimSuffix(wavName, ".wav")+".srt")
			_, txtErr := os.Stat(txtPath)
			_, srtErr := os.Stat(srtPath)
			list = append(list, RecordingInfo{
				Filename: wavName,
				Created:  info.ModTime().Format("15:04:05"),
				SizeKB:   math.Round(float64(info.Size())/1024.0*10) / 10,
				Status:   "done",
				HasText:  txtErr == nil,
				HasSRT:   srtErr == nil,
			})
		}
	}

	// 최신 파일 먼저
	sort.Slice(list, func(i, j int) bool {
		return list[i].Filename > list[j].Filename
	})

	w.Header().Set("Content-Type", "application/json")
	if list == nil {
		w.Write([]byte("[]"))
		return
	}
	json.NewEncoder(w).Encode(list)
}

// GET /api/text?topic=xxx&file=rec_xxx.wav (또는 .txt/.srt)
// memory/text/full 모드 모두 지원:
//   memory → resultMap(메모리)에서 반환
//   text   → 메모리 우선, 없으면 .txt 파일에서 반환
//   full   → 메모리 우선, 없으면 파일에서 반환
func handleText(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	topic := sanitizeName(r.URL.Query().Get("topic"))
	file  := sanitizeName(r.URL.Query().Get("file"))

	if topic == "" || file == "" {
		http.Error(w, "invalid params", 400)
		return
	}

	isSRT := strings.HasSuffix(file, ".srt")

	// .txt/.srt 확장자를 .wav로 정규화 → resultMap 키
	base := strings.TrimSuffix(strings.TrimSuffix(file, ".txt"), ".srt")
	if !strings.HasSuffix(base, ".wav") {
		base = base + ".wav"
	}
	key := topic + "::" + base

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")

	// 1. 메모리 우선 (모든 모드 공통)
	if res, ok := resultMapLoad(key); ok {
		if isSRT {
			w.Write([]byte(buildSRT(res.Segments)))
		} else {
			w.Write([]byte(res.Text))
		}
		return
	}

	// 2. 파일 폴백 (text/full 모드만)
	if saveMode == SaveModeText || saveMode == SaveModeFull {
		var filePath string
		if isSRT {
			filePath = filepath.Join(recBase, topic, strings.TrimSuffix(base, ".wav")+".srt")
		} else {
			filePath = filepath.Join(recBase, topic, strings.TrimSuffix(base, ".wav")+".txt")
		}
		if data, err := os.ReadFile(filePath); err == nil {
			w.Write(data)
			return
		}
	}

	http.Error(w, "not found", 404)
}

// POST /api/retranscribe?topic=xxx&file=rec_xxx.wav
// full 모드에서만 WAV 파일 기반 재처리 가능
func handleRetranscribe(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method != "POST" {
		http.Error(w, "POST only", 405)
		return
	}

	w.Header().Set("Content-Type", "application/json")

	if saveMode != SaveModeFull {
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "unavailable",
			"message": fmt.Sprintf("SAVE_MODE=%s: WAV 파일 미저장 모드에서는 재처리 불가 (full 모드 필요)", saveMode),
		})
		return
	}

	topic    := sanitizeName(r.URL.Query().Get("topic"))
	filename := sanitizeName(r.URL.Query().Get("file"))

	if topic == "" || filename == "" || !strings.HasSuffix(filename, ".wav") {
		http.Error(w, "invalid params", 400)
		return
	}

	wavPath := filepath.Join(recBase, topic, filename)
	wavBytes, err := os.ReadFile(wavPath)
	if err != nil {
		http.Error(w, "file not found", 404)
		return
	}

	key := topic + "::" + filename
	statusMap.Store(key, "queued")

	select {
	case sttQueue <- STTJob{topic, filename, wavBytes}:
		json.NewEncoder(w).Encode(map[string]string{"status": "queued"})
	default:
		http.Error(w, "queue full", 503)
	}
}

func sanitizeName(s string) string {
	s = filepath.Base(s)
	s = strings.Trim(s, "./\\")
	return s
}

// ── WebSocket 프록시 ──────────────────────────────────────────

func proxySTT(w http.ResponseWriter, r *http.Request) {
	client, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer client.Close()

	stt, _, err := websocket.DefaultDialer.Dial("ws://localhost:9001", nil)
	if err != nil {
		client.WriteMessage(websocket.TextMessage,
			[]byte(`{"type":"error","message":"STT 서버 연결 실패"}`))
		return
	}
	defer stt.Close()

	done := make(chan struct{}, 2)

	go func() {
		defer func() { done <- struct{}{} }()
		for {
			mt, msg, err := client.ReadMessage()
			if err != nil { break }
			if err := stt.WriteMessage(mt, msg); err != nil { break }
		}
	}()

	go func() {
		defer func() { done <- struct{}{} }()
		for {
			mt, msg, err := stt.ReadMessage()
			if err != nil { break }
			// stt_status 메시지는 /ws/live로도 브로드캐스트
			if mt == websocket.TextMessage {
				var msgData map[string]interface{}
				if err := json.Unmarshal(msg, &msgData); err == nil {
					if msgType, ok := msgData["type"].(string); ok && msgType == "stt_status" {
						broadcastJSON(msgData)
					}
				}
			}
			if err := client.WriteMessage(mt, msg); err != nil { break }
		}
	}()

	<-done
}

// ── CORS 헬퍼 ────────────────────────────────────────────────

func setCORS(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
}

// ── Legacy API (transcripts.jsonl) ───────────────────────────

func handleSave(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" { return }

	if r.Method == "DELETE" {
		mu.Lock(); defer mu.Unlock()
		os.Remove(dataFile)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "cleared"})
		return
	}

	if r.Method != "POST" { http.Error(w, "Method not allowed", 405); return }

	var e Entry
	if err := json.NewDecoder(r.Body).Decode(&e); err != nil {
		http.Error(w, "Bad request", 400)
		return
	}
	if e.Time    == "" { e.Time    = time.Now().Format("15:04:05") }
	if e.Speaker == "" { e.Speaker = "화자?" }

	mu.Lock(); defer mu.Unlock()

	f, err := os.OpenFile(dataFile, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil { http.Error(w, "File error", 500); return }
	defer f.Close()

	line, _ := json.Marshal(e)
	f.Write(line); f.WriteString("\n")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "time": e.Time})
}

func handleTranscripts(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" { return }

	mu.Lock()
	data, err := os.ReadFile(dataFile)
	mu.Unlock()

	entries := parseEntries(data)

	if r.URL.Query().Get("format") == "txt" {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.Header().Set("Content-Disposition", `attachment; filename="transcripts.txt"`)
		for _, e := range entries {
			known := ""
			if e.IsKnown { known = " ✓" }
			fmt.Fprintf(w, "[%s] %s%s: %s\n", e.Time, e.Speaker, known, e.Text)
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err != nil || len(entries) == 0 {
		w.Write([]byte("[]"))
		return
	}
	json.NewEncoder(w).Encode(entries)
}

func parseEntries(data []byte) []Entry {
	var entries []Entry
	start := 0
	for i := 0; i <= len(data); i++ {
		if i == len(data) || data[i] == '\n' {
			if i > start {
				var e Entry
				if json.Unmarshal(data[start:i], &e) == nil {
					entries = append(entries, e)
				}
			}
			start = i + 1
		}
	}
	return entries
}

// ── /api/hwinfo ───────────────────────────────────────────────
// STT 서버가 시작 시 저장한 hw_profile.json을 그대로 반환한다.
// STT 서버 미실행 시 기본 응답 반환.

func handleHWInfo(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == http.MethodOptions {
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")

	data, err := os.ReadFile("hw_profile.json")
	if err != nil {
		// STT 서버가 아직 실행 안 됐거나 파일 없음
		json.NewEncoder(w).Encode(map[string]interface{}{
			"tier":     "UNKNOWN",
			"device":   "unknown",
			"model":    "unknown",
			"compute":  "unknown",
			"cuda":     false,
			"cores":    0,
			"vram_gb":  0,
			"gpu_name": "STT 서버 미실행",
		})
		return
	}
	w.Write(data)
}

// ══════════════════════════════════════════════════════════════
//  저장소 관리 API
// ══════════════════════════════════════════════════════════════

// StorageFile: 단일 파일 메타데이터
type StorageFile struct {
	Filename string  `json:"filename"`
	Type     string  `json:"type"`     // "input" | "txt" | "srt"
	SizeKB   float64 `json:"sizeKB"`
	Modified string  `json:"modified"` // "YYYY-MM-DD HH:MM"
	Topic    string  `json:"topic"`
}

// StorageTopic: 주제별 집계
type StorageTopic struct {
	Topic    string        `json:"topic"`
	Inputs   int           `json:"inputs"`   // WAV 파일 수
	Outputs  int           `json:"outputs"`  // TXT+SRT 파일 수
	SizeKB   float64       `json:"sizeKB"`
	Files    []StorageFile `json:"files,omitempty"`
}

// StorageStats: 전체 통계
type StorageStats struct {
	Topics     int     `json:"topics"`
	TotalFiles int     `json:"totalFiles"`
	TotalSizeKB float64 `json:"totalSizeKB"`
	InputCount  int     `json:"inputCount"`
	OutputCount int     `json:"outputCount"`
	InputSizeKB float64 `json:"inputSizeKB"`
	OutputSizeKB float64 `json:"outputSizeKB"`
}

func scanRecordings() ([]StorageTopic, error) {
	entries, err := os.ReadDir(recBase)
	if err != nil {
		if os.IsNotExist(err) {
			return []StorageTopic{}, nil
		}
		return nil, err
	}

	var topics []StorageTopic
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		topic := e.Name()
		topicDir := filepath.Join(recBase, topic)

		files, err := os.ReadDir(topicDir)
		if err != nil {
			continue
		}

		st := StorageTopic{Topic: topic}
		for _, f := range files {
			if f.IsDir() {
				continue
			}
			info, err := f.Info()
			if err != nil {
				continue
			}
			sizeKB := float64(info.Size()) / 1024
			mod := info.ModTime().Format("2006-01-02 15:04")
			ext := strings.ToLower(filepath.Ext(f.Name()))

			var fType string
			switch ext {
			case ".wav":
				fType = "input"
				st.Inputs++
			case ".txt":
				fType = "txt"
				st.Outputs++
			case ".srt":
				fType = "srt"
				st.Outputs++
			default:
				continue
			}
			st.SizeKB += sizeKB
			st.Files = append(st.Files, StorageFile{
				Filename: f.Name(),
				Type:     fType,
				SizeKB:   math.Round(sizeKB*10) / 10,
				Modified: mod,
				Topic:    topic,
			})
		}
		topics = append(topics, st)
	}
	return topics, nil
}

// GET /api/storage/stats
func handleStorageStats(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == http.MethodOptions {
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")

	topics, err := scanRecordings()
	if err != nil {
		http.Error(w, `{"error":"scan failed"}`, 500)
		return
	}

	stats := StorageStats{Topics: len(topics)}
	for _, t := range topics {
		stats.TotalFiles += t.Inputs + t.Outputs
		stats.TotalSizeKB += t.SizeKB
		stats.InputCount += t.Inputs
		stats.OutputCount += t.Outputs
		for _, f := range t.Files {
			if f.Type == "input" {
				stats.InputSizeKB += f.SizeKB
			} else {
				stats.OutputSizeKB += f.SizeKB
			}
		}
	}
	stats.TotalSizeKB = math.Round(stats.TotalSizeKB*10) / 10
	stats.InputSizeKB = math.Round(stats.InputSizeKB*10) / 10
	stats.OutputSizeKB = math.Round(stats.OutputSizeKB*10) / 10

	json.NewEncoder(w).Encode(stats)
}

// GET /api/storage/topics
func handleStorageTopics(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == http.MethodOptions {
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")

	topics, err := scanRecordings()
	if err != nil {
		http.Error(w, `{"error":"scan failed"}`, 500)
		return
	}
	// Files 필드 제거 (목록만 반환)
	for i := range topics {
		topics[i].Files = nil
	}
	if topics == nil {
		topics = []StorageTopic{}
	}
	json.NewEncoder(w).Encode(topics)
}

// GET /api/storage/detail?topic=xxx
func handleStorageDetail(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == http.MethodOptions {
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")

	topic := r.URL.Query().Get("topic")
	if topic == "" {
		http.Error(w, `{"error":"topic required"}`, 400)
		return
	}

	topics, err := scanRecordings()
	if err != nil {
		http.Error(w, `{"error":"scan failed"}`, 500)
		return
	}
	for _, t := range topics {
		if t.Topic == topic {
			json.NewEncoder(w).Encode(t)
			return
		}
	}
	json.NewEncoder(w).Encode(StorageTopic{Topic: topic, Files: []StorageFile{}})
}

// DELETE /api/storage/delete?topic=xxx[&file=yyy]
// file 없으면 주제 전체 삭제, file 있으면 해당 파일만 삭제
func handleStorageDelete(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == http.MethodOptions {
		return
	}
	if r.Method != http.MethodDelete && r.Method != http.MethodPost {
		http.Error(w, "method not allowed", 405)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")

	topic := r.URL.Query().Get("topic")
	file  := r.URL.Query().Get("file")

	if topic == "" {
		http.Error(w, `{"error":"topic required"}`, 400)
		return
	}
	// 경로 탐색 방지
	topic = filepath.Base(topic)
	topicDir := filepath.Join(recBase, topic)

	if file == "" {
		// 주제 전체 삭제
		if err := os.RemoveAll(topicDir); err != nil {
			http.Error(w, `{"error":"delete failed"}`, 500)
			return
		}
		// metaMap, statusMap, resultMap 에서도 제거
		metaMap.Range(func(k, v interface{}) bool {
			if strings.HasPrefix(k.(string), topic+"::") {
				metaMap.Delete(k)
				statusMap.Delete(k)
				resultMap.Delete(k)
			}
			return true
		})
		json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "deleted": "topic:" + topic})
		return
	}

	// 단일 파일 삭제 (.wav 삭제 시 연관 .txt/.srt 도 함께 제거)
	file = filepath.Base(file)
	ext  := strings.ToLower(filepath.Ext(file))
	stem := strings.TrimSuffix(file, ext)

	var deleted []string
	toRemove := []string{filepath.Join(topicDir, file)}
	if ext == ".wav" {
		toRemove = append(toRemove,
			filepath.Join(topicDir, stem+".txt"),
			filepath.Join(topicDir, stem+".srt"),
		)
	}
	for _, p := range toRemove {
		if err := os.Remove(p); err == nil {
			deleted = append(deleted, filepath.Base(p))
		}
	}

	// 메모리 맵 정리
	key := topic + "::" + file
	metaMap.Delete(key)
	statusMap.Delete(key)
	resultMap.Delete(key)

	json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "deleted": deleted})
}

// DELETE /api/storage/delete-all — 전체 recordings 폴더 삭제 (주의: 모든 주제)
func handleStorageDeleteAll(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == http.MethodOptions {
		return
	}
	if r.Method != http.MethodDelete && r.Method != http.MethodPost {
		http.Error(w, "method not allowed", 405)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")

	// 확인 토큰 (클라이언트에서 "confirm=yes" 필드로 전송해야 함)
	confirm := r.URL.Query().Get("confirm")
	if confirm != "yes" {
		http.Error(w, `{"error":"confirm=yes required (destructive operation)"}`, 400)
		return
	}

	// 전체 recordings 폴더 삭제
	if err := os.RemoveAll(recBase); err != nil {
		http.Error(w, `{"error":"delete failed"}`, 500)
		return
	}

	// 메모리 맵 전체 정리
	metaMap.Range(func(k, v interface{}) bool {
		metaMap.Delete(k)
		statusMap.Delete(k)
		resultMap.Delete(k)
		return true
	})

	json.NewEncoder(w).Encode(map[string]interface{}{
		"ok":    true,
		"msg":   "전체 녹음 폴더 삭제 완료",
		"path":  recBase,
	})
}

// POST /api/transcript/merge?topic=xxx — 수동 모드: 개별 텍스트 파일 병합
// 특정 주제의 모든 .txt 파일을 읽어 시간순으로 정렬하여 하나의 transcript.txt 생성
func handleTranscriptMerge(w http.ResponseWriter, r *http.Request) {
	setCORS(w)
	if r.Method == "OPTIONS" {
		return
	}
	if r.Method != "POST" {
		http.Error(w, `{"error":"POST only"}`, http.StatusMethodNotAllowed)
		return
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")

	topic := sanitizeName(r.URL.Query().Get("topic"))
	if topic == "" {
		http.Error(w, `{"error":"topic required"}`, 400)
		return
	}

	topicDir := filepath.Join(recBase, topic)

	// 주제 폴더의 모든 .txt 파일 스캔
	entries, err := os.ReadDir(topicDir)
	if err != nil {
		http.Error(w, `{"error":"topic not found"}`, 400)
		return
	}

	var txtFiles []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".txt") && e.Name() != "transcript.txt" {
			txtFiles = append(txtFiles, e.Name())
		}
	}

	if len(txtFiles) == 0 {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"ok":  true,
			"msg": "병합할 파일이 없습니다",
		})
		return
	}

	// 파일명 시간순 정렬 (rec_HHMMSS_SSS.txt 형식)
	sort.Strings(txtFiles)

	// 각 파일의 내용을 읽어 순서대로 병합
	var merged []string
	for _, fname := range txtFiles {
		fpath := filepath.Join(topicDir, fname)
		content, err := os.ReadFile(fpath)
		if err == nil && len(content) > 0 {
			merged = append(merged, strings.TrimSpace(string(content)))
		}
	}

	// transcript.txt 작성
	transcriptPath := filepath.Join(topicDir, "transcript.txt")
	transcriptContent := strings.Join(merged, "\n")
	if err := os.WriteFile(transcriptPath, []byte(transcriptContent), 0644); err != nil {
		http.Error(w, `{"error":"write failed"}`, 500)
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"ok":    true,
		"msg":   fmt.Sprintf("%d개 파일 병합 완료", len(txtFiles)),
		"count": len(txtFiles),
		"path":  transcriptPath,
	})
}

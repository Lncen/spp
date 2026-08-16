/**
 * 新消息提醒：页面不在前台时弹系统通知 + 播放提示音。
 * 提示音会让浏览器在任务栏图标上显示“播放中”高亮，配合标题闪烁提醒用户。
 */

const NOTIFICATION_TAG = "new-message"
const CUE_FREQUENCY_HZ = 880
const CUE_DURATION_MS = 150
export const MESSAGE_CUE_VOLUME = "message_cue_volume"

const DEFAULT_CUE_VOLUME = 0.15

let audioContext: AudioContext | null = null
let cueVolume = DEFAULT_CUE_VOLUME

/** 设置新消息提示音音量（0~1），供全局设置同步 */
export function setMessageCueVolume(volume: number): void {
  cueVolume = Number.isFinite(volume)
    ? Math.min(1, Math.max(0, volume))
    : DEFAULT_CUE_VOLUME
}

function ensureAudioContext(): void {
  if (audioContext) {
    if (audioContext.state === "suspended") {
      audioContext.resume().catch(() => {})
    }
    return
  }
  const AudioContextCtor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext
  if (!AudioContextCtor) {
    return
  }
  audioContext = new AudioContextCtor()
  audioContext.resume().catch(() => {})
}

// 浏览器自动播放策略要求先有用户交互才能出声：
// 首次点击/按键时创建并恢复音频上下文，之后后台消息到来即可播放提示音。
function initAudioOnUserGesture(): void {
  const events = ["pointerdown", "keydown", "touchstart"] as const
  const handler = () => {
    ensureAudioContext()
    for (const event of events) {
      window.removeEventListener(event, handler)
    }
  }
  for (const event of events) {
    window.addEventListener(event, handler)
  }
}

if (typeof window !== "undefined") {
  initAudioOnUserGesture()
}

/** 播放新消息提示音（仅页面不在前台时），并让浏览器高亮任务栏图标 */
export function playMessageCue(): void {
  if (typeof window === "undefined" || document.hasFocus()) {
    return
  }
  if (cueVolume <= 0 || audioContext?.state !== "running") {
    return
  }
  const now = audioContext.currentTime
  const oscillator = audioContext.createOscillator()
  const gain = audioContext.createGain()
  oscillator.type = "sine"
  oscillator.frequency.value = CUE_FREQUENCY_HZ
  gain.gain.setValueAtTime(0.001, now)
  gain.gain.exponentialRampToValueAtTime(Math.max(0.001, cueVolume), now + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.001, now + CUE_DURATION_MS / 1000)
  oscillator.connect(gain)
  gain.connect(audioContext.destination)
  oscillator.start(now)
  oscillator.stop(now + CUE_DURATION_MS / 1000)
}

/** 弹系统通知（仅页面不在前台时），首次使用会请求浏览器通知权限 */
export function notifyNewMessage(title: string, body?: string): void {
  if (typeof window === "undefined" || document.hasFocus()) {
    return
  }
  if (!("Notification" in window)) {
    return
  }
  const show = () => {
    new Notification(title, {
      body,
      tag: NOTIFICATION_TAG,
    })
  }
  if (Notification.permission === "granted") {
    show()
    return
  }
  if (Notification.permission === "default") {
    Notification.requestPermission()
      .then((permission) => {
        if (permission === "granted") {
          show()
        }
      })
      .catch(() => {})
  }
}

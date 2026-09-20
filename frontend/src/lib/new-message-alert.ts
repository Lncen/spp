/**
 * 新消息提醒：页面不在前台时弹系统通知 + 播放提示音。
 * 提示音会让浏览器在任务栏图标上显示“播放中”高亮，配合标题闪烁提醒用户。
 */

const NOTIFICATION_TAG_PREFIX = "new-message"
const NOTIFICATION_ICON = "/assets/images/favicon.png"
const CUE_FREQUENCY_HZ = 880
const CUE_DURATION_MS = 150
export const MESSAGE_CUE_VOLUME = "message_cue_volume"

const DEFAULT_CUE_VOLUME = 0.15

/** 触发音频上下文 / 通知权限初始化所需的用户手势事件 */
const USER_GESTURE_EVENTS = ["pointerdown", "keydown", "touchstart"] as const

let audioContext: AudioContext | null = null
let cueVolume = DEFAULT_CUE_VOLUME

/** 设置新消息提示音音量（0~2，0 静音，2 为 2 倍），供全局设置同步 */
export function setMessageCueVolume(volume: number): void {
  cueVolume = Number.isFinite(volume)
    ? Math.min(2, Math.max(0, volume))
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
  const handler = () => {
    ensureAudioContext()
    for (const event of USER_GESTURE_EVENTS) {
      window.removeEventListener(event, handler)
    }
  }
  for (const event of USER_GESTURE_EVENTS) {
    window.addEventListener(event, handler)
  }
}

/**
 * 通知权限：在首次用户交互时就请求，而不是等到消息到达那一刻。
 * 浏览器只允许在用户手势中弹权限框，消息到达时通常不是手势上下文，
 * 请求会被静默忽略，结果就是「右下角一直不弹通知」。
 */
function initNotificationPermissionOnUserGesture(): void {
  if (!("Notification" in window) || Notification.permission !== "default") {
    return
  }
  const handler = () => {
    Notification.requestPermission().catch(() => {})
    for (const event of USER_GESTURE_EVENTS) {
      window.removeEventListener(event, handler)
    }
  }
  for (const event of USER_GESTURE_EVENTS) {
    window.addEventListener(event, handler)
  }
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

/**
 * 弹系统通知（仅页面不在前台时）

 * - `tagKey` 用于区分会话 / 通知：同一 key 的新通知替换旧的，不同 key 依次堆叠；
 *   固定 tag 会被 Windows 当作"同一通知"，用户划过之后容易被静默抑制；
 * - 权限被拒或页面不是安全上下文（HTTPS / localhost）时不弹，并打印可定位的告警。
 */
export function notifyNewMessage(
  title: string,
  body?: string,
  tagKey?: string,
): void {
  if (typeof window === "undefined" || document.hasFocus()) {
    return
  }
  if (!("Notification" in window)) {
    console.warn("[notify] 当前浏览器不支持桌面通知")
    return
  }
  if (!window.isSecureContext) {
    console.warn("[notify] 桌面通知需要 HTTPS 或 localhost，当前不是安全上下文")
    return
  }
  const show = () => {
    new Notification(title, {
      body,
      tag: `${NOTIFICATION_TAG_PREFIX}:${tagKey ?? Date.now()}`,
      icon: NOTIFICATION_ICON,
      // renotify 不在 TS 的 NotificationOptions 里（属于 Service Worker 通知选项），
      // 但 Chrome/Edge 的页面通知支持：同一 tag 更新时重新提醒，而不是静默替换
      renotify: true,
    } as NotificationOptions)
  }
  if (Notification.permission === "granted") {
    show()
    return
  }
  if (Notification.permission === "denied") {
    console.warn("[notify] 桌面通知被浏览器拒绝，请在站点设置里重新允许通知")
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

// 模块加载时注册一次性手势监听：首次交互即准备好音频上下文与通知权限
if (typeof window !== "undefined") {
  initAudioOnUserGesture()
  initNotificationPermissionOnUserGesture()
}

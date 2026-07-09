"""
RateLimiter 速率限制模块

对用户消息频率进行限制，防止刷屏。
通过高优先级消息处理器实现：当用户触发限流时调用 ``event.mark_processed()``
短路后续低优先级处理器，从而"拦截"消息。

支持两种限流策略：
- 固定窗口（fixed window）
- 滑动窗口（sliding window），更平滑

限流维度可选：按用户、按群、按用户+群组合。

i18n 翻译在 ``on_load`` 时通过 ``sdk.i18n.register()`` 注册，
``on_unload`` 时通过 ``sdk.i18n.unregister_domain()`` 清理。
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import message
from ErisPulse.loaders import ModuleLoadStrategy
from ErisPulse.runtime.config_schema import BaseConfig


# ==================== i18n 域名 ====================

_I18N_DOMAIN = "rate_limiter"

# ==================== 多语言翻译 ====================

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # -------------------- 简体中文 --------------------
    "zh-CN": {
        # 配置描述
        "rate_limiter.enabled": "是否启用速率限制",
        "rate_limiter.max_messages": "时间窗口内允许的最大消息数",
        "rate_limiter.window_seconds": "时间窗口大小（秒）",
        "rate_limiter.scope": "限流维度：user / group / user_group",
        "rate_limiter.strategy": "限流策略：fixed=固定窗口, sliding=滑动窗口",
        "rate_limiter.warn_message": "触发限流时的提示文案（留空则不提示，静默拦截）",
        "rate_limiter.private_limit": "是否对私聊消息也限流",
        "rate_limiter.whitelist": "白名单用户 ID 列表，这些用户不受限流（如管理员/Bot 所有者）",
        # select 选项标签
        "rate_limiter.option.scope.user": "按用户",
        "rate_limiter.option.scope.group": "按群",
        "rate_limiter.option.scope.user_group": "按用户+群",
        "rate_limiter.option.strategy.fixed": "固定窗口",
        "rate_limiter.option.strategy.sliding": "滑动窗口",
        # 占位符与分组标题
        "rate_limiter.warn_message.placeholder": "留空则静默拦截",
        "rate_limiter.whitelist.placeholder": "用逗号分隔多个用户 ID",
        "rate_limiter.group.basic": "基本设置",
        "rate_limiter.group.advanced": "高级设置",
        # 运行时消息
        "rate_limiter.log.loaded": "RateLimiter 已加载",
        "rate_limiter.log.unloaded": "RateLimiter 已卸载",
        "rate_limiter.log.config_updated": "限流配置已更新: {old}/{window}s → {new}/{window}s",
        "rate_limiter.log.warn_send_failed": "限流警告发送失败: {error}",
    },
    # -------------------- 繁体中文 --------------------
    "zh-TW": {
        "rate_limiter.enabled": "是否啟用速率限制",
        "rate_limiter.max_messages": "時間窗口內允許的最大訊息數",
        "rate_limiter.window_seconds": "時間窗口大小（秒）",
        "rate_limiter.scope": "限流維度：user / group / user_group",
        "rate_limiter.strategy": "限流策略：fixed=固定窗口, sliding=滑動窗口",
        "rate_limiter.warn_message": "觸發限流時的提示文案（留空則不提示，靜默攔截）",
        "rate_limiter.private_limit": "是否對私聊訊息也限流",
        "rate_limiter.whitelist": "白名單使用者 ID 列表，這些使用者不受限流（如管理員/Bot 擁有者）",
        "rate_limiter.option.scope.user": "按使用者",
        "rate_limiter.option.scope.group": "按群組",
        "rate_limiter.option.scope.user_group": "按使用者+群組",
        "rate_limiter.option.strategy.fixed": "固定窗口",
        "rate_limiter.option.strategy.sliding": "滑動窗口",
        # 占位符與分組標題
        "rate_limiter.warn_message.placeholder": "留空則靜默攔截",
        "rate_limiter.whitelist.placeholder": "用逗號分隔多個使用者 ID",
        "rate_limiter.group.basic": "基本設定",
        "rate_limiter.group.advanced": "進階設定",
        # 運行時消息
        "rate_limiter.log.loaded": "RateLimiter 已載入",
        "rate_limiter.log.unloaded": "RateLimiter 已卸載",
        "rate_limiter.log.config_updated": "限流設定已更新: {old}/{window}s → {new}/{window}s",
        "rate_limiter.log.warn_send_failed": "限流警告發送失敗: {error}",
    },
    # -------------------- English --------------------
    "en": {
        "rate_limiter.enabled": "Enable rate limiting",
        "rate_limiter.max_messages": "Maximum messages allowed within the time window",
        "rate_limiter.window_seconds": "Time window size (seconds)",
        "rate_limiter.scope": "Rate limit scope: user / group / user_group",
        "rate_limiter.strategy": "Rate limit strategy: fixed=fixed window, sliding=sliding window",
        "rate_limiter.warn_message": "Warning message when rate limited (empty = silent block)",
        "rate_limiter.private_limit": "Also apply rate limiting to private messages",
        "rate_limiter.whitelist": "Whitelisted user IDs, exempt from rate limiting (e.g. admins/bot owners)",
        "rate_limiter.option.scope.user": "Per user",
        "rate_limiter.option.scope.group": "Per group",
        "rate_limiter.option.scope.user_group": "Per user+group",
        "rate_limiter.option.strategy.fixed": "Fixed window",
        "rate_limiter.option.strategy.sliding": "Sliding window",
        # placeholders & group titles
        "rate_limiter.warn_message.placeholder": "Empty = silent block",
        "rate_limiter.whitelist.placeholder": "Comma-separated user IDs",
        "rate_limiter.group.basic": "Basic",
        "rate_limiter.group.advanced": "Advanced",
        # runtime messages
        "rate_limiter.log.loaded": "RateLimiter loaded",
        "rate_limiter.log.unloaded": "RateLimiter unloaded",
        "rate_limiter.log.config_updated": "Rate limit config updated: {old}/{window}s → {new}/{window}s",
        "rate_limiter.log.warn_send_failed": "Failed to send rate limit warning: {error}",
    },
    # -------------------- 日本語 --------------------
    "ja": {
        "rate_limiter.enabled": "レート制限を有効にする",
        "rate_limiter.max_messages": "時間枠内で許可される最大メッセージ数",
        "rate_limiter.window_seconds": "時間枠のサイズ（秒）",
        "rate_limiter.scope": "制限スコープ: user / group / user_group",
        "rate_limiter.strategy": "制限戦略: fixed=固定ウィンドウ, sliding=スライディングウィンドウ",
        "rate_limiter.warn_message": "レート制限時の警告メッセージ（空欄でサイレントブロック）",
        "rate_limiter.private_limit": "プライベートメッセージにも制限を適用",
        "rate_limiter.whitelist": "ホワイトリストユーザーID（管理者/Bot所有者など、制限対象外）",
        "rate_limiter.option.scope.user": "ユーザー単位",
        "rate_limiter.option.scope.group": "グループ単位",
        "rate_limiter.option.scope.user_group": "ユーザー+グループ単位",
        "rate_limiter.option.strategy.fixed": "固定ウィンドウ",
        "rate_limiter.option.strategy.sliding": "スライディングウィンドウ",
        # プレースホルダーとグループタイトル
        "rate_limiter.warn_message.placeholder": "空欄でサイレントブロック",
        "rate_limiter.whitelist.placeholder": "カンマ区切りでユーザーIDを指定",
        "rate_limiter.group.basic": "基本設定",
        "rate_limiter.group.advanced": "詳細設定",
        # 実行時メッセージ
        "rate_limiter.log.loaded": "RateLimiter がロードされました",
        "rate_limiter.log.unloaded": "RateLimiter がアンロードされました",
        "rate_limiter.log.config_updated": "レート制限設定が更新されました: {old}/{window}s → {new}/{window}s",
        "rate_limiter.log.warn_send_failed": "レート制限警告の送信に失敗: {error}",
    },
    # -------------------- Русский --------------------
    "ru": {
        "rate_limiter.enabled": "Включить ограничение частоты",
        "rate_limiter.max_messages": "Максимальное количество сообщений в окне",
        "rate_limiter.window_seconds": "Размер временного окна (сек)",
        "rate_limiter.scope": "Область ограничения: user / group / user_group",
        "rate_limiter.strategy": "Стратегия: fixed=фиксированное окно, sliding=скользящее окно",
        "rate_limiter.warn_message": "Предупреждение при ограничении (пусто = тихая блокировка)",
        "rate_limiter.private_limit": "Также применять к личным сообщениям",
        "rate_limiter.whitelist": "Белый список ID пользователей, освобождённых от ограничения",
        "rate_limiter.option.scope.user": "По пользователю",
        "rate_limiter.option.scope.group": "По группе",
        "rate_limiter.option.scope.user_group": "По пользователю+группе",
        "rate_limiter.option.strategy.fixed": "Фиксированное окно",
        "rate_limiter.option.strategy.sliding": "Скользящее окно",
        # Подсказки и названия групп
        "rate_limiter.warn_message.placeholder": "Пусто = тихая блокировка",
        "rate_limiter.whitelist.placeholder": "ID через запятую",
        "rate_limiter.group.basic": "Основные",
        "rate_limiter.group.advanced": "Расширенные",
        # Сообщения времени выполнения
        "rate_limiter.log.loaded": "RateLimiter загружен",
        "rate_limiter.log.unloaded": "RateLimiter выгружен",
        "rate_limiter.log.config_updated": "Настройки ограничения обновлены: {old}/{window}s → {new}/{window}s",
        "rate_limiter.log.warn_send_failed": "Не удалось отправить предупреждение: {error}",
    },
}


class LimitScope(str, Enum):
    """限流维度"""

    USER = "user"            # 按用户（跨群合并计数）
    GROUP = "group"          # 按群（群内所有人合并计数）
    USER_GROUP = "user_group"  # 按用户+群（每个用户在每个群独立计数）


@dataclass
class RateLimiterConfig(BaseConfig):
    """RateLimiter 模块配置"""

    enabled: bool = field(
        default=True,
        metadata={
            "description": {"i18n": "rate_limiter.enabled", "default": "是否启用速率限制"},
            "ui": {"widget": "switch", "group": "basic", "order": 1},
        },
    )
    max_messages: int = field(
        default=10,
        metadata={
            "description": {
                "i18n": "rate_limiter.max_messages",
                "default": "时间窗口内允许的最大消息数",
            },
            "ui": {"widget": "number", "group": "basic", "order": 2},
        },
    )
    window_seconds: int = field(
        default=10,
        metadata={
            "description": {
                "i18n": "rate_limiter.window_seconds",
                "default": "时间窗口大小（秒）",
            },
            "ui": {"widget": "number", "group": "basic", "order": 3},
        },
    )
    scope: str = field(
        default="user_group",
        metadata={
            "description": {
                "i18n": "rate_limiter.scope",
                "default": "限流维度：user / group / user_group",
            },
            "ui": {
                "widget": "select",
                "group": "basic",
                "order": 4,
                "options": [
                    {"label": {"i18n": "rate_limiter.option.scope.user", "default": "按用户"}, "value": "user"},
                    {"label": {"i18n": "rate_limiter.option.scope.group", "default": "按群"}, "value": "group"},
                    {"label": {"i18n": "rate_limiter.option.scope.user_group", "default": "按用户+群"}, "value": "user_group"},
                ],
            },
        },
    )
    strategy: str = field(
        default="sliding",
        metadata={
            "description": {
                "i18n": "rate_limiter.strategy",
                "default": "限流策略：fixed=固定窗口, sliding=滑动窗口",
            },
            "ui": {
                "widget": "select",
                "group": "advanced",
                "order": 5,
                "options": [
                    {"label": {"i18n": "rate_limiter.option.strategy.fixed", "default": "固定窗口"}, "value": "fixed"},
                    {"label": {"i18n": "rate_limiter.option.strategy.sliding", "default": "滑动窗口"}, "value": "sliding"},
                ],
            },
        },
    )
    warn_message: str = field(
        default="⚠️ 你的消息频率过高，请稍后再试",
        metadata={
            "description": {
                "i18n": "rate_limiter.warn_message",
                "default": "触发限流时的提示文案（留空则不提示，静默拦截）",
            },
            "ui": {"widget": "text", "group": "advanced", "order": 6, "placeholder": {"i18n": "rate_limiter.warn_message.placeholder", "default": "留空则静默拦截"}},
        },
    )
    private_limit: bool = field(
        default=True,
        metadata={
            "description": {
                "i18n": "rate_limiter.private_limit",
                "default": "是否对私聊消息也限流",
            },
            "ui": {"widget": "switch", "group": "advanced", "order": 7},
        },
    )
    whitelist: list = field(
        default_factory=list,
        metadata={
            "description": {
                "i18n": "rate_limiter.whitelist",
                "default": "白名单用户 ID 列表，这些用户不受限流（如管理员/Bot 所有者）",
            },
            "ui": {"widget": "text", "group": "advanced", "order": 8, "placeholder": {"i18n": "rate_limiter.whitelist.placeholder", "default": "用逗号分隔多个用户 ID"}},
        },
    )

    # 分组显示名（i18n），Dashboard 据此渲染分区标题
    _schema_meta = {
        "group_labels": {
            "basic": {"i18n": "rate_limiter.group.basic", "default": "基本设置"},
            "advanced": {"i18n": "rate_limiter.group.advanced", "default": "高级设置"},
        }
    }


class Main(BaseModule):
    """
    RateLimiter 速率限制模块

    工作原理：
    1. ``on_load`` 注册多语言翻译和高优先级消息处理器（priority=1000）
    2. 检查当前发送者在时间窗口内的消息计数
    3. 超限时调用 ``event.mark_processed()`` 短路后续处理器，并可选地回复警告
    4. ``on_unload`` 清理 i18n 域和计数器

    使用方式：安装并启用即可，无需调用任何方法。
    可在运行时通过配置热更新调整阈值。
    """

    ConfigClass = RateLimiterConfig

    def __init__(self, sdk):
        self.sdk = sdk
        self.logger = sdk.logger.get_child("RateLimiter")
        self.i18n = sdk.i18n
        # 固定窗口计数器: {key: (window_start_ts, count)}
        self._fixed_buckets: dict[str, tuple[float, int]] = {}
        # 滑动窗口时间戳队列: {key: [ts1, ts2, ...]}
        self._sliding_buckets: dict[str, list[float]] = defaultdict(list)

    @staticmethod
    def get_load_strategy() -> ModuleLoadStrategy | dict[str, Any]:
        """非懒加载、高优先级，确保在业务模块之前注册拦截器"""
        return ModuleLoadStrategy(lazy_load=False, priority=200)

    # ==================== i18n 注册 ====================

    def _register_i18n(self) -> None:
        """注册所有语言的翻译文本"""
        for lang, translations in _TRANSLATIONS.items():
            self.i18n.register(lang, translations, domain=_I18N_DOMAIN)

    def _unregister_i18n(self) -> None:
        """卸载本模块的 i18n 翻译"""
        self.i18n.unregister_domain(_I18N_DOMAIN)

    # ==================== 生命周期 ====================

    async def on_load(self, event: dict) -> bool:
        """模块加载：注册 i18n 翻译并注册限流拦截器"""
        self._register_i18n()
        self._register_interceptor()
        self.logger.info(self.i18n.t("rate_limiter.log.loaded"))
        return True

    async def on_unload(self, event: dict) -> bool:
        """模块卸载：清理 i18n 域并清空计数器"""
        self._fixed_buckets.clear()
        self._sliding_buckets.clear()
        self._unregister_i18n()
        self.logger.info(self.i18n.t("rate_limiter.log.unloaded"))
        return True

    def on_config_update(self, old_config, new_config):
        """配置热更新：清空计数器使新阈值立即生效"""
        self.logger.info(
            self.i18n.t(
                "rate_limiter.log.config_updated",
                old=f"{old_config.max_messages}",
                new=f"{new_config.max_messages}",
                window=new_config.window_seconds,
            )
        )
        self._fixed_buckets.clear()
        self._sliding_buckets.clear()

    # ==================== 拦截器注册 ====================

    def _register_interceptor(self):
        """注册高优先级消息拦截器"""

        @message.on_message(priority=1000)
        async def rate_limit_interceptor(event):
            await self._check(event)

    # ==================== 限流核心 ====================

    async def _check(self, event) -> None:
        """检查单条消息是否超限，超限则拦截"""
        cfg = self.cfg
        if not cfg.enabled:
            return

        # 私聊不限流（按配置）
        if event.is_private_message() and not cfg.private_limit:
            return

        user_id = event.get_user_id()

        # 白名单免疫（管理员 / Bot 所有者）
        if user_id and cfg.whitelist and user_id in cfg.whitelist:
            return

        key = self._build_key(event, cfg.scope, user_id)
        if key is None:
            return  # 无法识别发送者，放行

        # 校验策略值，非法时回退到 sliding
        strategy = cfg.strategy if cfg.strategy in ("fixed", "sliding") else "sliding"
        allowed = self._consume(key, cfg.max_messages, cfg.window_seconds, strategy)
        if allowed:
            return  # 未超限，放行

        # 超限：拦截后续处理器
        event.mark_processed()

        if cfg.warn_message:
            try:
                await event.reply(cfg.warn_message)
            except Exception as e:
                self.logger.warning(
                    self.i18n.t("rate_limiter.log.warn_send_failed", error=e)
                )

    def _build_key(self, event, scope: str, user_id: str = "") -> str | None:
        """根据 scope 构建限流键"""
        if not user_id:
            user_id = event.get_user_id()
        group_id = event.get_group_id() or ""

        if scope == LimitScope.USER.value:
            return f"u:{user_id}" if user_id else None
        if scope == LimitScope.GROUP.value:
            # 仅对群消息生效，私聊无 group 维度
            return f"g:{group_id}" if group_id else None
        # user_group
        if not user_id:
            return None
        return f"ug:{user_id}:{group_id}"

    def _consume(self, key: str, max_count: int, window: int, strategy: str) -> bool:
        """
        消费一次配额

        :return: True=允许, False=被限流
        """
        now = time.time()
        if strategy == "fixed":
            return self._fixed_consume(key, max_count, window, now)
        return self._sliding_consume(key, max_count, window, now)

    def _fixed_consume(
        self, key: str, max_count: int, window: int, now: float
    ) -> bool:
        """固定窗口：窗口内计数，窗口结束重置"""
        window_start, count = self._fixed_buckets.get(key, (now, 0))
        if now - window_start >= window:
            # 进入新窗口，重置
            window_start, count = now, 0
        if count >= max_count:
            self._fixed_buckets[key] = (window_start, count)
            return False
        self._fixed_buckets[key] = (window_start, count + 1)
        return True

    def _sliding_consume(
        self, key: str, max_count: int, window: int, now: float
    ) -> bool:
        """滑动窗口：保留窗口内时间戳，超出窗口的旧记录剔除"""
        bucket = self._sliding_buckets[key]
        threshold = now - window
        # 剔除过期记录
        while bucket and bucket[0] < threshold:
            bucket.pop(0)
        if len(bucket) >= max_count:
            return False
        bucket.append(now)
        return True


__all__ = ["Main", "RateLimiterConfig", "LimitScope"]

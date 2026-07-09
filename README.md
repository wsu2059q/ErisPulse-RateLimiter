# ErisPulse RateLimiter Module / ErisPulse RateLimiter 速率限制模块

[English](#english) | [中文](#中文)

---

## English

[ErisPulse](https://github.com/ErisPulse/ErisPulse) message rate limiting module to prevent user spam.

### Features

- **Dual Strategy**: Fixed window and sliding window (recommended)
- **Multi-dimensional**: By user / by group / by user+group combo
- **Whitelist Immunity**: Admins and bot owners can be configured to bypass limits
- **Silent or Warn**: Optional warning message when rate limit is triggered
- **Hot Reload**: Runtime config changes take effect immediately
- **Full i18n**: Config descriptions, option labels, placeholders, and group titles all support multiple languages
- **Zero Intrusion**: Uses high-priority event interception — business modules don't need to be aware

### How It Works

The module registers a high-priority message handler (`priority=1000`) that executes before all business modules.
It checks the sender's message count within the time window. When the limit is exceeded, it calls `event.mark_processed()`
to short-circuit subsequent lower-priority handlers, effectively "intercepting" the message.

```
Message event flow:
  [RateLimiter interceptor priority=1000]
        ↓ whitelist user → pass through
        ↓ under limit   → pass through
        ↓ over limit    → mark_processed() → business modules won't execute
  [Business modules priority=0~999]
```

### Installation

```bash
pip install ErisPulse-RateLimiter
```

Or in development mode:

```bash
pip install -e .
```

### Configuration

After installing and starting ErisPulse, a `[RateLimiter]` section will be automatically generated in `config/config.toml`:

```toml
[RateLimiter]
enabled = true                    # Enable/disable
max_messages = 10                 # Max messages allowed in the time window
window_seconds = 10               # Time window size (seconds)
scope = "user_group"              # Scope: user / group / user_group
strategy = "sliding"              # Strategy: fixed / sliding
warn_message = "⚠️ Your message frequency is too high, please try again later"  # Warning text (leave empty for silent)
private_limit = true              # Whether to also limit private messages
whitelist = []                    # Whitelist user IDs, these users are exempt
```

#### Scope Explanation

| scope | Meaning | Use Case |
|-------|---------|----------|
| `user` | By user (cross-group aggregate count) | Prevent a single user from spamming globally |
| `group` | By group (everyone in the group aggregated) | Limit overall group activity |
| `user_group` | By user + group (independent count) | Precise to "a user in a group", most common |

#### Strategy Explanation

| strategy | Meaning | Characteristics |
|----------|---------|-----------------|
| `fixed` | Fixed window | Simple implementation, window boundaries may allow 2x traffic bursts |
| `sliding` | Sliding window (recommended) | Smoother, strictly ensures no window exceeds the limit |

### Example

Typical config: max 5 messages per user per group within 10 seconds, admins exempt.

```toml
[RateLimiter]
enabled = true
max_messages = 5
window_seconds = 10
scope = "user_group"
strategy = "sliding"
warn_message = "Please slow down, you're sending messages too quickly"
whitelist = ["admin_001", "admin_002"]
```

### Development

This module demonstrates ErisPulse's **event interception pattern** (high priority + `mark_processed()` short-circuit).
Refer to the [ErisPulse Module Development Guide](https://github.com/ErisPulse/ErisPulse/tree/main/docs/zh-CN/developer-guide) for more info.

---

## 中文

[ErisPulse](https://github.com/ErisPulse/ErisPulse) 的消息速率限制模块，防止用户刷屏。

### 功能特性

- **双策略限流**：固定窗口、滑动窗口（推荐）
- **多维度限流**：按用户 / 按群 / 按用户+群组合
- **白名单免疫**：管理员 / Bot 所有者可配置不受限流
- **静默或提示**：超限时可选回复警告文案
- **热更新**：运行时修改配置阈值立即生效
- **全面 i18n**：配置描述、选项标签、占位符、分组标题均支持多语言
- **零侵入**：通过高优先级事件拦截实现，业务模块无需感知

### 工作原理

模块注册一个 `priority=1000` 的高优先级消息处理器，先于所有业务模块执行。
检查发送者在时间窗口内的消息计数，超限时调用 `event.mark_processed()`
短路后续低优先级处理器，从而"拦截"消息。

```
消息事件流：
  [RateLimiter 拦截器 priority=1000]
        ↓ 白名单用户 → 直接放行
        ↓ 未超限   → 放行
        ↓ 超限     → mark_processed() → 业务模块不执行
  [业务模块 priority=0~999]
```

### 安装

```bash
pip install ErisPulse-RateLimiter
```

或开发模式：

```bash
pip install -e .
```

### 配置

安装并启动 ErisPulse 后，会自动在 `config/config.toml` 生成 `[RateLimiter]` 段：

```toml
[RateLimiter]
enabled = true                    # 是否启用
max_messages = 10                 # 时间窗口内允许的最大消息数
window_seconds = 10               # 时间窗口大小（秒）
scope = "user_group"              # 限流维度：user / group / user_group
strategy = "sliding"              # 限流策略：fixed / sliding
warn_message = "⚠️ 你的消息频率过高，请稍后再试"  # 触发限流时的提示（留空则静默拦截）
private_limit = true              # 是否对私聊消息也限流
whitelist = []                    # 白名单用户 ID，这些用户不受限流
```

#### 限流维度说明

| scope | 含义 | 适用场景 |
|-------|------|----------|
| `user` | 按用户（跨群合并计数） | 防止单个用户全局刷屏 |
| `group` | 按群（群内所有人合并） | 限制群整体活跃度 |
| `user_group` | 按用户+群（独立计数） | 精确到"某用户在某群"，最常用 |

#### 限流策略说明

| strategy | 含义 | 特点 |
|----------|------|------|
| `fixed` | 固定窗口 | 实现简单，窗口边界可能瞬时通过 2 倍流量 |
| `sliding` | 滑动窗口（推荐） | 更平滑，严格保证任意窗口内不超过上限 |

### 示例

典型配置：每用户每群 10 秒内最多 5 条消息，管理员免疫限流。

```toml
[RateLimiter]
enabled = true
max_messages = 5
window_seconds = 10
scope = "user_group"
strategy = "sliding"
warn_message = "请放慢速度哦，消息太频繁了"
whitelist = ["admin_001", "admin_002"]
```

### 开发

本模块演示了 ErisPulse 的 **事件拦截模式**（高优先级 + `mark_processed()` 短路）。
参考 [ErisPulse 模块开发指南](https://github.com/ErisPulse/ErisPulse/tree/main/docs/zh-CN/developer-guide) 了解更多。
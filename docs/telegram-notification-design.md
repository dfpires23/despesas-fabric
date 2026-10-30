# Telegram Notification Design — Outbox Pattern

**Goal**: guarantee that every expense loaded into the Warehouse eventually generates exactly the notifications the user expects, surviving any transient failure, while allowing manual, surgical correction of individual messages.

## 1. Mechanism

- A control column exists on each fact table that can trigger a notification: `Notificado_Telegram BIT`. **Fabric Warehouse does not support `DEFAULT` constraints**, so this column has no default value — every `INSERT` that populates these tables must set it explicitly to `0`.
- A dedicated Pipeline activity — decoupled from the ingestion notebook — runs **after** the Warehouse load is committed:
  1. `SELECT ... WHERE Notificado_Telegram = 0`
  2. Sends **one Telegram message per expense** (not batched).
  3. Stores the returned `message_id` in a new column (`Telegram_Message_Id`), linking each expense permanently to its Telegram message.
  4. Marks `Notificado_Telegram = 1` **per row**, only after a confirmed successful send.
- If the activity fails partway (network issue, Telegram API outage), unsent rows simply remain at `0` and are picked up automatically on the next scheduled run (or an immediate retry). No in-memory state is relied upon.

## 2. Manual resend / correction workflow

To resend or correct notifications (whether due to a failed send, manual deletion, or a corrected expense value), manually run:

`UPDATE ... SET Notificado_Telegram = 0 WHERE Carimbo_Original = @value`

The next pipeline run will process pending rows and send a new message. Existing messages are never edited (`editMessageText` is not used): this supports corrections noticed days later, well outside any reasonable edit window, and matches the preferred workflow of manually deleting the outdated message in Telegram before the resend goes out. No UI (e.g., Power App) will be built for this process; SQL-based updates remain the intended long-term workflow.
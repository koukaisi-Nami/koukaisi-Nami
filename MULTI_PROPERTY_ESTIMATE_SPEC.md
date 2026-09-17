# Multi-property estimate input

## Goal
Nami accepts several LINE attachments in one request (PDFs and/or photos), groups pages/images by property, and returns a separate estimate for each property.

## Required behavior
- Accept mixed PDF + image inputs across consecutive messages in the same active estimate session.
- Do not assume one attachment equals one property. Identify property boundaries using property name, room number, address, rent and document context.
- Images/pages that clearly belong to the same property are combined before estimating.
- Different properties must never have fees mixed together.
- If grouping is ambiguous, ask which image/page belongs to which property instead of guessing.
- Output one fixed-format estimate block per property.
- Keep unknown values as `－`.
- Brokerage fee is `－` unless the user explicitly specifies it for that estimate. Never infer brokerage from the drawing, company defaults, or prior estimates.
- User can apply one brokerage instruction to all properties (e.g. `全部仲介なし`) or target one property (e.g. `A物件だけ0.5ヶ月`).
- Preserve the standard order: 当月前家賃 / 次月前家賃 / 敷金 / 礼金 / 初回保証料 / 仲介手数料 / 火災保険 / 24時間サポート / 鍵交換 / 事務手数料 / 合計.
- Management/common fees are included in current/next advance rent, not shown separately.
- If move-in date is unspecified, current-month advance rent is `－`.

## Session behavior
Attachments may arrive as separate LINE webhook events. Store each attachment analysis in a temporary estimate batch keyed by conversation + requesting user. The batch stays open for a short window and is finalized by phrases such as `この物件全部見積もり`, `見積もり出して`, or equivalent.

## Safety
Never combine two properties merely because they were uploaded close together. When property identity cannot be determined reliably, return a grouping confirmation question.

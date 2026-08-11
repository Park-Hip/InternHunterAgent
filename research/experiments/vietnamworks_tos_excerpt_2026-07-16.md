# VietnamWorks Terms of Service — excerpt archive (T0019.1)

**Source URL:** https://www.vietnamworks.com/thoa-thuan-su-dung
**Fetched:** 2026-07-16 15:26 GMT · **HTTP status:** 200 OK · `Server: nginx`
**Page title:** "Thỏa Thuận Sử Dụng" (Terms & Conditions of Use)
**Last-updated / effective date:** **not shown anywhere on the page.** No version
number, no "last revised" line, no effective date. Recorded as *unknown*.
**Language:** Vietnamese only. No English version is linked from this page.

**How this page was located:** `https://www.vietnamworks.com/` footer → "Thỏa thuận sử dụng".
URLs tried that do **not** exist (both 404 → redirect to `/404`):
`https://www.vietnamworks.com/dieu-khoan-su-dung`, `https://www.vietnamworks.com/terms-of-service`.

**Method:** page fetched with `curl`, HTML tags stripped, full text searched for the
keywords listed under "Negative findings" below. The page is server-rendered, so the
full ToS text is present in the initial HTML response (40,404 chars of text after
tag-stripping — this is the real document, not a JS shell).

> **Translations below are mine (Claude), not official.** VietnamWorks publishes this
> document in Vietnamese only. The Vietnamese is quoted verbatim and is authoritative;
> the English is provided for the maintainer's convenience and must not be relied on as
> the legal text.

**Section headings present on the page** (13):
1. Chấp Thuận Điều Khoản & Điều Kiện · 2. Dịch Vụ Của VietnamWorks · 3. Dịch Vụ Đặt Mua
Và Thanh Toán · 4. Điều Khoản Về Sử Dụng Dịch Vụ · 5. Quyền Và Trách Nhiệm Của Người Sử
Dụng · 6. Các Vùng Tương Tác · 7. Các Quyền Sở Hữu Trí Tuệ · 8. Các Liên Kết, Từ Chối Các
Bảo Đảm, Giới Hạn Trách Nhiệm · 9. Tuân Thủ Và Xử Lý Vi Phạm · 10. Bồi Thường · 11. Bảo
Mật · 12. Cơ chế bảo mật thanh toán · 13. Các Vấn Đề Khác

---

## Negative findings — the decisive one

**There is no clause anywhere in this ToS prohibiting automated access, robots, spiders,
crawlers, scraping, or API use.** These terms do not appear in the document at all.

Full-text search over the stripped page (case-insensitive) for each of the following
returned **zero matches**:

`robot` · `spider` · `crawler` · `crawl` · `scrape` · `scraping` · `bot` · `API` ·
`giao diện lập trình` (API) · `dịch ngược` (reverse-engineer) · `reverse engineer` ·
`trích xuất` (extract) · `rút trích` (extract) · `hàng loạt` (bulk) ·
`phần mềm tự động` (automated software) · `công cụ tự động` (automated tool)

Terms that **did** match were reviewed individually; every relevant hit is quoted below.
Sections reviewed in full for automated-access language: **§3** (refusal of service),
**§4** (terms of use), **§5** (user rights & responsibilities), **§7** (intellectual
property), **§9** (compliance & handling of violations).

---

## Clause 1 — the only clause using "tự động" (automated): it is about ACCOUNTS, not access

Located in §4/§5, in the enumerated list of prohibited conduct.

> **Đăng ký tài khoản số lượng lớn và Tự động.** Các tài khoản được đăng ký một cách tự
> động và/hoặc có hệ thống với số lượng lớn, theo toàn quyền đánh giá của Công ty, được
> xem là vi phạm và sẽ áp dụng các xử lý vi phạm theo quy định tại Điều Khoản và Điều
> Kiện này.

*Translation (mine):* "**Bulk and Automated account registration.** Accounts registered
in an automated and/or systematic manner in large numbers shall, at the Company's sole
discretion, be deemed a violation and the violation-handling provisions of these Terms
and Conditions shall apply."

**Relevance:** this is the closest the ToS comes to the word "automated", and it governs
**registering accounts**, not fetching content. The pipeline registers no account and
sends no credentials (`userId: 0`). This clause does not reach the pipeline's conduct.

---

## Clause 2 — "improper purpose" (discretionary, purpose-based)

Same enumerated list, immediately following Clause 1.

> **Hoạt động không đúng mục đích.** Bất kỳ hành vi lạm dụng và/hoặc sử dụng website
> VietnamWorks sai lệch khỏi mục đích tuyển dụng, tìm kiếm cơ hội việc làm, theo toàn
> quyền đánh giá bởi Công ty, sẽ có thể được xem là vi phạm và sẽ bị áp dụng các xử lý vi
> phạm theo quy định tại Điều Khoản và Điều Kiện này.

*Translation (mine):* "**Activity for an improper purpose.** Any abuse of and/or use of
the VietnamWorks website deviating from the purpose of recruitment or of seeking
employment opportunities may, at the Company's sole discretion, be deemed a violation,
and the violation-handling provisions of these Terms and Conditions shall apply."

**Relevance:** purpose-based and explicitly discretionary ("theo toàn quyền đánh giá bởi
Công ty" — at the Company's sole discretion). It does not name automated access. A
job-search Q&A demo is arguably within "tìm kiếm cơ hội việc làm" (seeking employment
opportunities), but this is the Company's call to make, not ours. Flagged for the
maintainer; it is not an explicit prohibition on automated access.

---

## Clause 3 — intellectual property (§7) — **the clause that actually bites**

> Bạn đồng ý và thừa nhận rằng tất cả các nội dung trên VietnamWorks Website bao gồm
> nhưng không giới hạn bởi các sơ yếu lý lịch sẽ thuộc quyền sở hữu trí tuệ duy nhất của
> Website VietnamWorks và Navigos Group và **bạn không được quyền thay đổi, sao chép, mô
> phỏng, truyền, phân phối, công bố, tạo ra các sản phẩm phái sinh, hiển thị hoặc chuyển
> giao, hoặc khai thác nhằm mục đích thương mại bất kỳ phần nào của nội dung, toàn bộ hay
> từng phần.** Tuy nhiên, bạn có thể (i) tạo một bản sao dưới dạng số hoặc hình thức khác
> để phần cứng và phần mềm máy tính của bạn có thể truy cập và xem được nội dung, (ii) in
> một bản sao của từng đoạn nội dung, (iii) tạo và phân phối một số lượng hợp lý các bản
> sao nội dung, toàn bộ hay từng phần, ở dạng bản in hoặc bản điện tử **để dùng nội bộ**.

*Translation (mine):* "You agree and acknowledge that all content on the VietnamWorks
Website, including but not limited to résumés, shall be the sole intellectual property of
the VietnamWorks Website and Navigos Group, and **you are not entitled to modify, copy,
reproduce, transmit, distribute, publish, create derivative works from, display or
transfer, or commercially exploit any part of the content, in whole or in part.**
However, you may (i) create one copy in digital or other form so that your computer
hardware and software can access and view the content, (ii) print one copy of each
portion of the content, (iii) create and distribute a reasonable number of copies of the
content, in whole or in part, in printed or electronic form, **for internal use**."

And, closing the same section:

> Bất kể các bản sao hoặc việc sử dụng trái phép nào đối với nội dung nào cho mục đích
> thương mại sẽ bị coi là vi phạm và bị xử lý theo quy định có liên quan của pháp luật và
> các điều khoản quy định tại bản thỏa thuận này.

*Translation (mine):* "Any unauthorised copies or use of any content for commercial
purposes shall be deemed a violation and handled under the relevant provisions of the law
and the terms of this agreement."

**Relevance — read this one carefully.** This clause says nothing about *how* content is
obtained (automated or manual) and so does not trigger the T0019.1 decision rule, which
turns on automated access. But it constrains **what may be done with content once
obtained**: copying, storing, republishing, and derivative works are restricted, with a
carve-out for **internal use**. The pipeline copies postings into a database and the demo
displays them publicly. That is a *retention and display* question, not an *access*
question — and it is a question the deployed snapshot already raises today, independently
of any cron. See the Consequence line in `research/archive/deployment-research-plan.md` §11.

---

## Clause 4 — refusal of service (§3), for completeness

> Công ty bảo lưu quyền từ chối cung cấp dịch vụ cho các cá nhân, tổ chức, mà theo quy
> định của pháp luật hoặc theo toàn quyền đánh giá của Công ty: […] **Khai thác, sử dụng
> các thông tin được cung cấp bởi dịch vụ của Công ty không nhằm phục vụ cho mục đích
> tuyển dụng cho chính cá nhân, tổ chức đó**; và/hoặc Cung cấp các sản phẩm, dịch vụ mang
> tính chất cạnh tranh với các dịch vụ hiện có của VietnamWorks.

*Translation (mine):* "The Company reserves the right to refuse to provide services to
individuals or organisations which, under the law or at the Company's sole discretion:
[…] **exploit or use information provided by the Company's service other than to serve
that individual's or organisation's own recruitment purposes**; and/or provide products
or services competing with VietnamWorks' existing services."

**Relevance:** framed as grounds for **refusing or terminating service to a customer**,
and the listed remedies are all account-directed (terminate service, remove job ads,
disable the account, refund unused fees). We hold no account and buy no service, so the
remedies have no purchase on us. It nonetheless signals the Company's intent regarding
non-recruitment reuse of its listing data, which is why it is recorded here rather than
omitted.

---

## Summary for the decision rule

| Question | Answer |
|---|---|
| Does the ToS explicitly prohibit automated access / scraping / crawlers / API use? | **No.** Those terms do not appear in the document. |
| Is there any clause using "automated"? | Yes — Clause 1, governing **bulk account registration** only. Does not reach the pipeline. |
| Is there a clause restricting what we do with fetched content? | **Yes — Clause 3 (§7 IP).** Restricts copying/republishing; carve-out for internal use. Not an access prohibition; flagged as a caveat. |
| ToS last-updated date | **Unknown** — not shown on the page. |

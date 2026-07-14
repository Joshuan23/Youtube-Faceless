# The Quietloop Playbook — digital product

A one-time-purchase digital product ($49) that monetizes the Quietloop brand
with **zero fulfillment work**: buyer pays, platform delivers the file, done.

- `index.html` — the sales page (self-contained, deploys anywhere static)
- `product/quietloop-playbook.html` — **the product buyers pay for.**
  Do NOT deploy this folder to your public site. Deliver it only through
  the payment platform. (Tip: print it to PDF from a browser —
  File → Print → Save as PDF — and sell the PDF; it feels more like a
  "product" and can't be hot-linked.)

## Set up payments (~15 minutes, then fully hands-off)

Recommended: **Lemon Squeezy** — it's a merchant of record, meaning it
handles global sales tax/VAT for you, delivers the file automatically,
and manages refunds. Gumroad works identically; Stripe Payment Links are
fine too but leave sales tax to you.

1. Create a free account at [lemonsqueezy.com](https://lemonsqueezy.com)
   (or [gumroad.com](https://gumroad.com)).
2. New product → "Digital download" → upload the playbook PDF
   (print `product/quietloop-playbook.html` to PDF first).
3. Price: $49. Enable "customers get updates" if offered.
4. Copy your checkout link.
5. In `index.html`, set:

   ```js
   var CHECKOUT_URL = "";           // ← paste your link here
   ```

6. Deploy `playbook/index.html` (GitHub Pages / Netlify / Vercel —
   same options as `landing/README.md`). **Exclude `product/`.**

That's the whole business loop: traffic → sales page → platform checkout →
automatic delivery. Nothing per-sale for you to do.

## Where traffic comes from (pick one and repeat)

- The Quietloop waitlist (cross-sell in your launch email)
- LinkedIn/X posts showing ONE blueprint working end-to-end
- Communities where agency owners live (r/agency, Slack groups) — share a
  blueprint free, link the rest
- The cold-outreach list: anyone who replied "not now" to the agency offer
  is a $49 yes

## Pricing notes

- $49 launch / $79 regular is the impulse-purchase band for B2B operators —
  under approval-needed territory, high enough to signal quality.
- Add an "agency license" tier later (~$199, deploy-for-clients) — it's the
  same file with a different license line, and often 20–30% of revenue.

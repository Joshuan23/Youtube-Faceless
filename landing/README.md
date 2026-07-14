# Quietloop — landing page

A single-file, dependency-free landing page for **Quietloop**, an AI automation
studio. Everything (styles, fonts, scripts) is inlined in `index.html`, so it
deploys anywhere that serves static files.

## Preview locally

```bash
cd landing
python3 -m http.server 8080
# open http://localhost:8080
```

## Deploy

Any static host works — no build step:

- **GitHub Pages**: Settings → Pages → deploy from branch, folder `/landing`
  (or copy `index.html` to the repo root of a `quietloop` repo).
- **Netlify / Vercel / Cloudflare Pages**: drag-and-drop the `landing` folder
  or point the project at it with no build command.

## Wire up the waitlist (2 minutes)

Out of the box, signups are stored in the visitor's own browser
(`localStorage` key `quietloop-waitlist`) — fine for previewing, useless for
launch. To collect emails for real:

1. Create a free form endpoint at [formspree.io](https://formspree.io) (or
   [web3forms.com](https://web3forms.com), or your own API).
2. In `index.html`, find:

   ```js
   var WAITLIST_ENDPOINT = "";
   ```

3. Set it to your endpoint, e.g.:

   ```js
   var WAITLIST_ENDPOINT = "https://formspree.io/f/YOUR_FORM_ID";
   ```

The form POSTs JSON: `{ "email": "...", "source": "quietloop-landing" }`.
A honeypot field (`company_site`) filters basic bots.

## Notes

- **Fonts**: Bricolage Grotesque (latin subset, variable weight) is embedded
  as a base64 `@font-face` — no external font requests.
- **Dark mode**: follows the visitor's OS preference automatically; both
  themes are designed, not inverted.
- **The "ops console"** in the hero is a simulated demo (labeled as such in
  the markup) and respects `prefers-reduced-motion`.
- Name check: before printing business cards, verify `quietloop`
  trademark/domain availability in your jurisdiction.

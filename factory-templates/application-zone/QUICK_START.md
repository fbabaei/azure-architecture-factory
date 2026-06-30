# 🚀 GPS Guide - 5-Minute Quick Start

**Goal:** Add a professional GPS guide to your app  
**Time:** 5 minutes  
**Difficulty:** ⭐ Easy

---

## Copy-Paste Path 📋

```
FROM:  factory-templates/application-zone/GPS_GUIDE_TEMPLATE_WRAPPER.html
TO:    packs/[your-app]/1.0.0/GPS_GUIDE.html
```

---

## The 3 Things to Change

Open your new `GPS_GUIDE.html` and find the `appConfig` object. Change these 3 lines:

```javascript
const appConfig = {
    appName: "Your App Name",      // ← CHANGE #1: Your app name
    agentCount: 6,                 // ← CHANGE #2: Number of agents YOU have
    runtimePort: 8000,             // ← CHANGE #3: Port YOUR app uses (if different)
    startStage: 0,
    stages: [
        // Copy from gps-config.template.json and paste here
        // ↓ ↓ ↓
    ]
};
```

---

## Get Your Stages (2 Minutes)

### Option A: Use Generic Template (Recommended First Time)
1. Open: `gps-config.template.json`
2. Copy: The entire `stages` array
3. Paste: Into your `GPS_GUIDE.html` where it says `stages: [ ... ]`
4. Done! ✅

### Option B: Customize (After it works)
1. Open: `gps-config.template.json`
2. Edit: Stage names, descriptions, tips (customize for YOUR app)
3. Copy: The modified stages array
4. Paste: Into your `GPS_GUIDE.html`
5. Done! ✅

---

## Test It (1 Minute)

```
1. Save your GPS_GUIDE.html
2. Open in browser: packs/[your-app]/1.0.0/GPS_GUIDE.html
3. Verify:
   ✓ See your app name in header
   ✓ See 6 stage dots (🚀 ⚙️ 📦 🔍 ⚡ 🎯)
   ✓ Click stage → see description
   ✓ Click checklist items → they mark as complete
   ✓ See Previous/Next buttons
   ✓ Progress bar fills as you advance
```

---

## 5-Minute Checklist ✅

- [ ] Copied `GPS_GUIDE_TEMPLATE_WRAPPER.html`
- [ ] Renamed to `GPS_GUIDE.html`
- [ ] Changed `appName`
- [ ] Changed `agentCount`
- [ ] Changed `runtimePort` (if needed)
- [ ] Added `stages` array
- [ ] Saved file
- [ ] Tested in browser
- [ ] All 6 stages visible
- [ ] Interactions work

---

## Common Edits

### Edit Stage Name
```javascript
{
    name: "🚀 My Custom Name",  // ← Edit here
    // ...
}
```

### Edit Stage Description
```javascript
{
    description: "My custom description of what happens at this stage...",  // ← Edit here
    // ...
}
```

### Edit Checklist Items
```javascript
{
    checklist: [
        "My first task",     // ← Edit these
        "My second task",
        "My third task"
    ],
    // ...
}
```

### Edit Tips
```javascript
{
    tip: "💡 My helpful tip for users",  // ← Edit here
    // ...
}
```

---

## I Don't Know How Many Stages I Need

**Answer:** You always need 6 stages.

**Why?** The template is designed for 6 stages (shown as 6 dots). If you have different workflow, adapt your workflow to 6 stages:

```
Stage 0: Start/Welcome
Stage 1: Setup/Environment
Stage 2: Create Instance
Stage 3: Discover/Load Resources
Stage 4: Invoke/Take Action
Stage 5: Results/Next Steps
```

---

## I'm Stuck

### GPS won't load (loading spinner forever)
- ✅ Check: Is `GPS_GUIDE_TEMPLATE.html` in parent directory? (should be at `../../GPS_GUIDE_TEMPLATE.html`)
- ✅ Check browser console (F12 → Console) for errors
- ✅ Verify file path in fetch() call matches

### Stages don't show
- ✅ Check: Did you paste the stages array completely?
- ✅ Check: Is the JSON valid? (use jsonlint.com)
- ✅ Check: No missing commas?

### Buttons don't work
- ✅ Check: Is JavaScript enabled?
- ✅ Check: Are there console errors? (F12 → Console)
- ✅ Check: Did you change the function names?

### Wrong app name showing
- ✅ Check: Did you change `appName` field?
- ✅ Check: Did you save the file?
- ✅ Check: Did you refresh browser (Ctrl+F5)?

---

## I Want to Customize Colors

**Edit in:** `GPS_GUIDE_TEMPLATE.html` (not your app's GPS_GUIDE.html)

Find this line in the template:
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
/* Change these hex colors to YOUR brand colors */
```

Options:
- `#667eea` = Purple
- `#764ba2` = Purple (darker)
- Change to your colors, save, all apps inherit

---

## I Want Different Number of Stages

**Not recommended** for consistency, but technically possible.

Edit in your `GPS_GUIDE.html`:
```javascript
stages: [
    /* 3 stages instead of 6 */
]
```

The template auto-generates dots for however many stages you provide.

---

## I Have a Different Workflow

Adapt your workflow to the 6-stage model:

```
Your Workflow:          Maps To:
1. Login               → Stage 0: Start
2. Load app           → Stage 1: Setup
3. Create project     → Stage 2: Create Instance
4. Import data        → Stage 3: Discover
5. Process/Run        → Stage 4: Invoke
6. Export results     → Stage 5: Results
```

---

## Need Full Documentation?

- **GPS_ONBOARDING_FOR_NEW_APPS.md** - Complete step-by-step guide
- **GPS_GUIDE_ARCHITECTURE.md** - How the system works
- **gps-config.template.json** - All fields explained
- **GPS_GUIDE_TEMPLATE.html** - Reference implementation

---

## Summary

1. Copy wrapper → Rename → Customize 3 fields → Paste stages → Test
2. You now have a professional GPS guide for your app
3. Portal auto-embeds it in the "🗺️ GPS Guide" tab

**That's it!** 🎉

---

**Questions?** See GPS_ONBOARDING_FOR_NEW_APPS.md for more details.

# 🚀 Adding GPS Guide to Your New App

**Time to complete: 5 minutes**

This guide walks you through adding a GPS Guide to your application so users know exactly where they are in their journey.

---

## The Big Picture

```
Your App's manifest.json
         ↓
    Contains: agents, services, channels
         ↓
GPS Guide reads manifest → Shows user journey
         ↓
User sees: 6-stage interactive guide
```

---

## 3-Step Process (Easy! ✨)

### STEP 1️⃣: Copy the Boilerplate (30 seconds)

**Do this:**
1. Go to: `factory-templates/application-zone/`
2. Copy `GPS_GUIDE_TEMPLATE_WRAPPER.html`
3. Paste it in your app's pack folder
4. Rename to `GPS_GUIDE.html`

**Example:**
```
packs/
  └── my-new-app/
      └── 1.0.0/
          ├── manifest.json        ← your app's agents
          └── GPS_GUIDE.html       ← newly copied wrapper ✅
```

---

### STEP 2️⃣: Customize the Configuration (2 minutes)

**Open your new `GPS_GUIDE.html` and find this section:**

```javascript
// STEP 1: Define your app's GPS configuration
const appConfig = {
    appName: "Your App Name",           // ← CHANGE THIS
    subtitle: "Your custom subtitle",   // ← OPTIONAL
    agentCount: 6,                      // ← CHANGE TO YOUR COUNT
    runtimePort: 8000,                  // ← CHANGE IF NEEDED
    startStage: 0,
    stages: [
        // ← ADD YOUR STAGES HERE (copy from template)
    ]
};
```

**Easy replacements:**

| Item | What to do | Example |
|------|-----------|---------|
| `appName` | Your app's name | `"MyAI Assistant"` |
| `agentCount` | How many agents you expose | `3` or `6` or `10` |
| `runtimePort` | Port your app listens on | `8001` or `3000` |
| `stages` | Copy-paste from `gps-config.template.json` | See Step 3 ⬇️ |

---

### STEP 3️⃣: Add Your Stages (2 minutes)

**Option A: Generic (Recommended for your first app)**

Copy the entire `stages` array from `gps-config.template.json` and paste it into your `GPS_GUIDE.html`:

```javascript
stages: [
    {
        number: 0,
        emoji: "🚀",
        name: "🚀 Let's Begin!",
        timing: "1 minute",
        description: "Welcome to the Application Zone...",
        // ... rest of stage
    },
    {
        number: 1,
        emoji: "⚙️",
        name: "⚙️ Setup Your Environment",
        // ... etc
    }
    // ... 4 more stages
]
```

**Option B: Custom (If you want something unique)**

Edit the stages in `gps-config.template.json` to match YOUR app's workflow, then copy them:

```javascript
stages: [
    {
        number: 0,
        emoji: "🎯",                        // Your emoji
        shortName: "Start",                 // Short label for breadcrumb
        name: "🎯 My Custom Start Screen",  // Full stage name
        timing: "1 minute",
        description: "My custom description of what happens here",
        details: {
            title: "What you'll do:",
            items: [
                "My first step",
                "My second step"
            ]
        },
        tip: "My helpful tip for users",
        substages: ["Sub 1", "Sub 2", "Sub 3"],
        checklist: [
            "Check item 1",
            "Check item 2",
            "Check item 3"
        ],
        landmark: "You completed this stage when..."
    }
    // Add 5 more stages for stages 1-5
]
```

---

## Stage Template Structure

**Copy this for EACH stage you add:**

```javascript
{
    number: 0,                          // 0-5 (which stage in the journey)
    emoji: "🚀",                        // Stage emoji (for journey dots)
    shortName: "Start",                 // Short name (for breadcrumbs)
    name: "🚀 Let's Begin!",            // Full stage name
    timing: "1 minute",                 // Estimated time
    description: "Long description of what happens at this stage...",
    details: {
        title: "What you'll learn:",
        items: [
            "Item 1",
            "Item 2",
            "Item 3"
        ]
    },
    tip: "💡 Helpful tip for users",
    substages: [
        "Substep 1",
        "Substep 2",
        "Substep 3"
    ],
    checklist: [
        "Checkbox item 1",
        "Checkbox item 2",
        "Checkbox item 3"
    ],
    landmark: "You'll know you're done when..."
}
```

---

## That's It! 🎉

Your GPS Guide is now ready. Test it:

1. Open your manifest's `GPS_GUIDE.html` in a browser
2. Click through the 6 stages
3. Try clicking checklist items
4. Verify the stage titles match your app

---

## Verify It Works

**In browser, your GPS should show:**

- ✅ 6 journey dots (🚀 ⚙️ 📦 🔍 ⚡ 🎯)
- ✅ Progress bar that fills as you advance
- ✅ Current stage details with description
- ✅ Interactive checklist (click items to mark done)
- ✅ Previous/Next buttons to navigate
- ✅ Breadcrumb navigation at the top

**If something's missing:**
1. Check console for errors (F12 → Console)
2. Make sure `GPS_GUIDE_TEMPLATE.html` is in the parent directory
3. Verify all `stages` are in the config

---

## Integration: Factory Portal

To make the GPS guide appear in the Factory Portal's tabbed interface:

1. In `factory-portal.html`, the iframe already points to your GPS guide
2. When users click "🗺️ GPS Guide" tab, they see your stages
3. No additional work needed! The portal auto-loads whatever GPS_GUIDE.html you provide

---

## Examples

### Example 1: Minimal (5 min to complete)

Copy `gps-config.template.json` → Paste into your GPS_GUIDE.html → Done ✅

### Example 2: Custom (15 min to complete)

1. Copy template
2. Customize stage names/descriptions/tips for YOUR app
3. Add custom emojis if desired
4. Test in browser

### Example 3: Advanced (30 min)

1. Create totally custom stages
2. Add company branding colors (edit CSS in template)
3. Add company-specific tips and landmarks
4. Link to your docs

---

## For the Impatient: Copy-Paste Path

```
factory-templates/application-zone/GPS_GUIDE_TEMPLATE_WRAPPER.html
    ↓ copy & rename
packs/your-app/1.0.0/GPS_GUIDE.html
    ↓ edit appConfig
{
    appName: "Your App",
    agentCount: YOUR_COUNT,
    stages: [ /* copy from gps-config.template.json */ ]
}
    ↓ save
    ↓ DONE! Open in browser and test
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Loading..." spinner never finishes | Template path wrong. Make sure `GPS_GUIDE_TEMPLATE.html` is in parent directory |
| Blank page | Check browser console (F12) for JavaScript errors |
| Stages don't show | Verify `stages` array is valid JSON (use jsonlint.com if unsure) |
| Emojis don't render | Some systems need UTF-8. Ensure HTML has `<meta charset="UTF-8">` |
| Buttons don't work | Check that `goToStage()` function exists (it's in the template) |

---

## Next: Register in Portal

Once your GPS_GUIDE.html is working:

1. Add to your `manifest.json`:
   ```json
   "metadata": {
       "gpsGuide": "GPS_GUIDE.html"
   }
   ```

2. Factory Portal will auto-detect and include your guide in the tabbed interface

3. Users see it when they click "🗺️ GPS Guide"

---

## Need Help?

- Stuck on stages? Copy `gps-config.template.json` as-is first. Get it working, then customize.
- Questions about emoji? Use these recommended: 🚀 ⚙️ 📦 🔍 ⚡ 🎯
- Want to change colors? Edit CSS in `GPS_GUIDE_TEMPLATE.html` (purple gradients by default)

---

**That's all! Your users now have a crystal-clear journey guide.** 🗺️✨


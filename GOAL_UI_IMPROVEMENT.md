# Premium UI Overhaul Goal

Your goal is to drastically overhaul the user interface of our Streamlit application (`app/main.py`) to achieve a world-class, premium enterprise SaaS aesthetic. The end result must look hand-crafted and award-winning, completely eliminating any generic, default, or "AI-generated" appearance. 

Apply the high-end design tactics, CSS properties, and aesthetic principles gathered from our recent context enrichment regarding award-winning UI trends.

## Core Requirements:

1. **Immersive Hero Section:**
   - Implement a massive, full-screen (or near full-screen) hero area.
   - It must include a large, high-quality background image slider or a highly dynamic, premium background (e.g., subtle animated gradients or high-res visuals).
   - Use custom HTML/CSS injected via `st.markdown` to bypass Streamlit's default layout constraints for this section.

2. **Premium Card Designs:**
   - Redesign all metric and info cards to look ultra-premium.
   - Employ modern UI techniques such as glassmorphism (backdrop-filter), subtle multi-layered drop shadows, refined border-radii, and delicate border highlights.
   - Add micro-animations (e.g., smooth hover effects with slight scaling or shadow expansion).

3. **Elegant Data Tables:**
   - Overhaul the styling of data tables.
   - Ensure ample padding, clean and modern typography, distinct header styling, and elegant row hover states.
   - The tables must feel like a core part of a high-end dashboard, not just standard HTML tables.

4. **Cohesive Design System:**
   - Maintain and elevate the use of modern typography (e.g., the 'Outfit' font already in use).
   - Apply a sophisticated, harmonious color palette throughout the application. Ensure high contrast and accessibility while maintaining a sleek, modern look (e.g., deep dark mode with vibrant accent colors or a pristine light mode).

## Implementation Guidelines:
- **Codebase:** All UI changes should be primarily made in `app/main.py` by aggressively expanding the `inject_custom_css` function and using `st.markdown(..., unsafe_allow_html=True)` for custom HTML components.
- **Functionality:** Do not break existing application logic (parsing, production engine, finance engine, etc.). The goal is purely visual enhancement.
- **Version Control:** You are authorized to commit your changes and push directly to the `main` branch once the visual overhaul is complete and verified. Use a descriptive commit message like `feat(ui): implement premium award-winning UI overhaul`.

Execute this goal systematically. First, implement the base CSS framework and hero section, then move on to cards and tables. Review the visual output frequently to ensure it meets the "wow" factor requirement.

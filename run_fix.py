#!/usr/bin/env python
with open('reporting/generator.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Normalize line endings first
text = text.replace('\r\n', '\n')

# The HTML sections need fixing
text = text.replace(
    'result.min_yield_safety_factor:.2f</div>',
    'result.min_yield_safety_factor:.2f</div> if result.min_yield_safety_factor is not None else "N/A</div>"'
)
text = text.replace(
    'model.constraints.min_yield_safety_factor:.2f</div>',
    'model.constraints.min_yield_safety_factor:.2f</div> if model.constraints.min_yield_safety_factor is not None else "N/A</div>"'
)
text = text.replace(
    'result.min_fatigue_safety_factor:.2f</div>',
    'result.min_fatigue_safety_factor:.2f</div> if result.min_fatigue_safety_factor is not None else "N/A</div>"'
)

# Write back
with open('reporting/generator.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print('Done fixing HTML sections')

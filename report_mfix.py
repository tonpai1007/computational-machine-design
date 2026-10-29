import sys

try:
    with open('reporting/generator.py', 'rb') as f:
        content = f.read()

    # Decode, normalize, fix, encode back
    text = content.decode('utf-8')

    # Normalize line endings
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    # Fix the three None formatting issues in HTML report
    # Note: include the \n after </div> in the search pattern
    text = text.replace(
        'result.min_yield_safety_factor:.2f</div>\n',
        'result.min_yield_safety_factor:.2f</div>\n if result.min_yield_safety_factor is not None else "N/A</div>"'
    )
    text = text.replace(
        'model.constraints.min_yield_safety_factor:.2f</div>\n',
        'model.constraints.min_yield_safety_factor:.2f</div>\n if model.constraints.min_yield_safety_factor is not None else "N/A</div>"'
    )
    text = text.replace(
        'result.min_fatigue_safety_factor:.2f</div>\n',
        'result.min_fatigue_safety_factor:.2f</div>\n if result.min_fatigue_safety_factor is not None else "N/A</div>"'
    )

    # Write back as bytes preserving \n line endings
    content = text.encode('utf-8')
    with open('reporting/generator.py', 'wb') as f:
        f.write(content)

    print("Successfully fixed reporting/generator.py")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

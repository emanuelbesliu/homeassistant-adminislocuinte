# Home Assistant Dashboard Examples

This guide shows you how to create beautiful and functional dashboards to display your Adminis Locuințe data in Home Assistant.

## Available Sensors

After setting up the integration, you'll have the following sensors:

### Global Sensors (Account-wide)
- `sensor.adminis_locuinte_location_count` - Number of properties
- `sensor.adminis_locuinte_total_pending` - Total pending payments
- `sensor.adminis_locuinte_last_payment_amount` - Last payment amount
- `sensor.adminis_locuinte_last_payment_date` - Last payment date

### Per-Location Sensors (created for each property)
For each location (e.g., apartment 12 - ID 123456):
- `sensor.adminis_locuinte_12_monthly_bill` - Current/latest monthly bill
- `sensor.adminis_locuinte_12_pending` - Pending payments for this location
- `sensor.adminis_locuinte_12_last_payment` - Last payment for this location

## Dashboard Example 1: Simple Overview Card

Perfect for a quick glance at your utility bills.

```yaml
type: entities
title: Adminis Locuințe - Overview
entities:
  - entity: sensor.adminis_locuinte_location_count
    name: Properties
    icon: mdi:home-group
  - entity: sensor.adminis_locuinte_total_pending
    name: Total Pending
    icon: mdi:cash-multiple
  - entity: sensor.adminis_locuinte_last_payment_amount
    name: Last Payment
    icon: mdi:receipt
  - entity: sensor.adminis_locuinte_last_payment_date
    name: Payment Date
    icon: mdi:calendar-check
```

## Dashboard Example 2: Detailed Per-Location Cards

Shows detailed information for each property.

```yaml
type: vertical-stack
cards:
  # Apartment 12
  - type: entities
    title: Apartament 12
    icon: mdi:home
    entities:
      - entity: sensor.adminis_locuinte_12_monthly_bill
        name: Latest Bill
        icon: mdi:file-document
      - entity: sensor.adminis_locuinte_12_pending
        name: Pending Amount
        icon: mdi:cash-clock
      - entity: sensor.adminis_locuinte_12_last_payment
        name: Last Payment
        icon: mdi:receipt-text-check
  
  # Parking Space P5
  - type: entities
    title: Parcare P5
    icon: mdi:car
    entities:
      - entity: sensor.adminis_locuinte_p5_monthly_bill
        name: Latest Bill
        icon: mdi:file-document
      - entity: sensor.adminis_locuinte_p5_pending
        name: Pending Amount
        icon: mdi:cash-clock
      - entity: sensor.adminis_locuinte_p5_last_payment
        name: Last Payment
        icon: mdi:receipt-text-check
```

## Dashboard Example 3: Gauge Cards for Visual Appeal

Shows pending and last payment as gauges.

```yaml
type: horizontal-stack
cards:
  - type: gauge
    entity: sensor.adminis_locuinte_last_payment_amount
    name: Last Payment
    unit: RON
    min: 0
    max: 2000
    severity:
      green: 0
      yellow: 800
      red: 1200
  
  - type: gauge
    entity: sensor.adminis_locuinte_total_pending
    name: Pending
    unit: RON
    min: 0
    max: 2000
    severity:
      green: 0
      yellow: 500
      red: 1000
```

## Dashboard Example 4: Payment Breakdown Card

Shows the detailed breakdown of charges from the last payment.

```yaml
type: markdown
title: Last Payment Breakdown
content: |
  ## Last Payment: {{ states('sensor.adminis_locuinte_last_payment_amount') }} RON
  **Date:** {{ states('sensor.adminis_locuinte_last_payment_date') }}
  
  ### Breakdown:
  {% set breakdown = state_attr('sensor.adminis_locuinte_last_payment_amount', 'breakdown') %}
  {% if breakdown %}
  {% for item, amount in breakdown.items() %}
  - **{{ item }}**: {{ amount }} RON
  {% endfor %}
  {% else %}
  No breakdown available
  {% endif %}
```

## Dashboard Example 5: Complete Dashboard Layout

A comprehensive dashboard combining all elements.

```yaml
title: Adminis Locuințe
views:
  - title: Overview
    path: overview
    icon: mdi:home
    cards:
      # Summary Row
      - type: horizontal-stack
        cards:
          - type: gauge
            entity: sensor.adminis_locuinte_last_payment_amount
            name: Last Payment
            unit: RON
            min: 0
            max: 2000
            severity:
              green: 0
              yellow: 800
              red: 1200
          
          - type: gauge
            entity: sensor.adminis_locuinte_total_pending
            name: Total Pending
            unit: RON
            min: 0
            max: 2000
            severity:
              green: 0
              yellow: 500
              red: 1000
      
      # Quick Stats
      - type: glance
        title: Quick Stats
        entities:
          - entity: sensor.adminis_locuinte_location_count
            name: Properties
          - entity: sensor.adminis_locuinte_last_payment_date
            name: Last Payment
          - entity: sensor.adminis_locuinte_total_pending
            name: Pending
      
      # Apartment 12 Details
      - type: entities
        title: Apartament 12
        icon: mdi:home
        show_header_toggle: false
        entities:
          - entity: sensor.adminis_locuinte_12_monthly_bill
            name: Monthly Bill
            icon: mdi:file-document
          - entity: sensor.adminis_locuinte_12_pending
            name: Pending
            icon: mdi:cash-clock
          - entity: sensor.adminis_locuinte_12_last_payment
            name: Last Payment
            icon: mdi:receipt-text-check
      
      # Parking P5 Details
      - type: entities
        title: Parcare P5
        icon: mdi:car
        show_header_toggle: false
        entities:
          - entity: sensor.adminis_locuinte_p5_monthly_bill
            name: Monthly Bill
            icon: mdi:file-document
          - entity: sensor.adminis_locuinte_p5_pending
            name: Pending
            icon: mdi:cash-clock
          - entity: sensor.adminis_locuinte_p5_last_payment
            name: Last Payment
            icon: mdi:receipt-text-check
  
  - title: Payment History
    path: history
    icon: mdi:history
    cards:
      # Payment Breakdown
      - type: markdown
        title: Last Payment Breakdown
        content: |
          ## Payment Details
          **Amount:** {{ states('sensor.adminis_locuinte_last_payment_amount') }} RON  
          **Date:** {{ states('sensor.adminis_locuinte_last_payment_date') }}  
          **Location:** {{ state_attr('sensor.adminis_locuinte_last_payment_amount', 'location_id') }}
          
          ### Charge Breakdown:
          {% set breakdown = state_attr('sensor.adminis_locuinte_last_payment_amount', 'breakdown') %}
          {% if breakdown %}
          | Charge | Amount (RON) |
          |--------|--------------|
          {% for item, amount in breakdown.items() %}
          | {{ item }} | {{ amount }} |
          {% endfor %}
          
          **Total:** {{ states('sensor.adminis_locuinte_last_payment_amount') }} RON
          {% else %}
          No breakdown data available
          {% endif %}
      
      # History Graph (requires history integration)
      - type: history-graph
        title: Payment History
        entities:
          - entity: sensor.adminis_locuinte_last_payment_amount
        hours_to_show: 720  # 30 days
```

## Dashboard Example 6: Mobile-Friendly Card

Optimized for mobile viewing.

```yaml
type: picture-elements
image: /local/apartment_background.jpg  # Optional background image
elements:
  - type: state-label
    entity: sensor.adminis_locuinte_last_payment_amount
    prefix: "Last Payment: "
    suffix: " RON"
    style:
      top: 30%
      left: 50%
      color: white
      font-size: 24px
      font-weight: bold
  
  - type: state-label
    entity: sensor.adminis_locuinte_total_pending
    prefix: "Pending: "
    suffix: " RON"
    style:
      top: 50%
      left: 50%
      color: yellow
      font-size: 20px
      font-weight: bold
  
  - type: state-label
    entity: sensor.adminis_locuinte_last_payment_date
    prefix: "Paid on: "
    style:
      top: 70%
      left: 50%
      color: white
      font-size: 16px
```

## Dashboard Example 7: Utility Category Breakdown

If you want to track specific utilities separately, create template sensors:

```yaml
# In configuration.yaml
template:
  - sensor:
      - name: "Water Total"
        unit_of_measurement: "RON"
        state: >
          {% set breakdown = state_attr('sensor.adminis_locuinte_12_monthly_bill', 'breakdown') %}
          {% if breakdown %}
            {{ (breakdown.get('Apa calda', 0) + breakdown.get('Apa rece', 0) + breakdown.get('Dif.apa calda', 0)) | float }}
          {% else %}
            0
          {% endif %}
      
      - name: "Heating Total"
        unit_of_measurement: "RON"
        state: >
          {% set breakdown = state_attr('sensor.adminis_locuinte_12_monthly_bill', 'breakdown') %}
          {% if breakdown %}
            {{ (breakdown.get('Incalzire', 0) + breakdown.get('Agent Termic', 0)) | float }}
          {% else %}
            0
          {% endif %}
      
      - name: "Services Total"
        unit_of_measurement: "RON"
        state: >
          {% set breakdown = state_attr('sensor.adminis_locuinte_12_monthly_bill', 'breakdown') %}
          {% if breakdown %}
            {{ (breakdown.get('Curatenie', 0) + breakdown.get('Serviciu paza', 0) + breakdown.get('Ascensor', 0)) | float }}
          {% else %}
            0
          {% endif %}
```

Then display them:

```yaml
type: entities
title: Utility Breakdown
entities:
  - entity: sensor.water_total
    name: Water
    icon: mdi:water
  - entity: sensor.heating_total
    name: Heating
    icon: mdi:radiator
  - entity: sensor.services_total
    name: Services
    icon: mdi:room-service
```

## Dashboard Example 8: Bar Chart (requires custom card)

If you have `apexcharts-card` installed:

```yaml
type: custom:apexcharts-card
header:
  title: Monthly Expenses by Category
  show: true
series:
  - entity: sensor.water_total
    name: Water
  - entity: sensor.heating_total
    name: Heating
  - entity: sensor.services_total
    name: Services
chart_type: bar
```

## Tips for Customization

1. **Icons**: Use `mdi:` icons from [Material Design Icons](https://materialdesignicons.com/)
2. **Colors**: Customize with `style:` in YAML or use card-mod
3. **Notifications**: Create automations to notify when pending > 0 or new bill available
4. **Graphs**: Enable the `history` integration for historical data
5. **Custom Cards**: Install community cards like `apexcharts-card`, `mini-graph-card`, or `mushroom-cards`

## Automation Example: Bill Payment Reminder

```yaml
automation:
  - alias: "Adminis - Payment Reminder"
    trigger:
      - platform: state
        entity_id: sensor.adminis_locuinte_total_pending
    condition:
      - condition: numeric_state
        entity_id: sensor.adminis_locuinte_total_pending
        above: 0
    action:
      - service: notify.mobile_app
        data:
          title: "Utilities Payment Due"
          message: "You have {{ states('sensor.adminis_locuinte_total_pending') }} RON pending for utilities."
```

## Troubleshooting

- **Sensors not showing?** Wait 5 minutes after setup for first data refresh
- **Missing breakdown?** Check that payment history contains data
- **Template errors?** Ensure you're using the correct entity IDs for your locations

---

**Need help?** Check the integration logs in Home Assistant: Settings → System → Logs

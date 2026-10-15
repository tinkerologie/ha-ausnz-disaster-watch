import { LitElement, html, css } from "lit";

interface LovelaceCardConfig {
  type: string;
  title?: string;
  entity?: string;
  max_incidents?: number;
  show_map_button?: boolean;
}

interface IncidentItem {
  id: string;
  title: string;
  hazard_type: string;
  warning_level: string;
  distance_km?: number;
  location_name?: string;
  responsible_agency?: string;
  web_url?: string;
  status?: string;
  updated_at?: string;
}

interface HomeAssistant {
  states: Record<string, any>;
  navigate: (_path: string) => void;
}

export class AusDisasterCard extends LitElement {
  private _config?: LovelaceCardConfig;
  private _hass?: HomeAssistant;
  private _filter: string = "all";

  static override properties = {
    _config: { state: true },
    _hass: { state: true },
    _filter: { state: true },
  };

  static override styles = css`
    :host {
      display: block;
    }
    ha-card {
      padding: 16px;
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0, 0, 0, 0.1));
      background: var(--ha-card-background, var(--card-background-color, #fff));
      color: var(--primary-text-color, #212121);
      font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
      overflow: hidden;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .title {
      font-size: 1.15rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .banner {
      padding: 12px 16px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-weight: 600;
      margin-bottom: 16px;
      color: #fff;
      transition: background-color 0.3s ease;
    }
    .banner-emergency {
      background: #d32f2f;
      animation: pulse 2s infinite;
    }
    .banner-watch-and-act {
      background: #e65100;
    }
    .banner-advice {
      background: #f57f17;
      color: #212121;
    }
    .banner-clear {
      background: #2e7d32;
    }
    @keyframes pulse {
      0% {
        box-shadow: 0 0 0 0 rgba(211, 47, 47, 0.6);
      }
      70% {
        box-shadow: 0 0 0 10px rgba(211, 47, 47, 0);
      }
      100% {
        box-shadow: 0 0 0 0 rgba(211, 47, 47, 0);
      }
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      margin-bottom: 16px;
    }
    .stat-card {
      background: var(--secondary-background-color, #f5f5f5);
      border-radius: 8px;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
    }
    .stat-label {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .stat-value {
      font-size: 1.2rem;
      font-weight: 700;
      margin-top: 4px;
    }
    .filters {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
      overflow-x: auto;
      padding-bottom: 4px;
    }
    .filter-chip {
      background: var(--secondary-background-color, #f0f0f0);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 16px;
      padding: 4px 12px;
      font-size: 0.8rem;
      cursor: pointer;
      user-select: none;
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    .filter-chip.active {
      background: var(--primary-color, #0288d1);
      color: #fff;
      border-color: var(--primary-color, #0288d1);
    }
    .incidents-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 380px;
      overflow-y: auto;
    }
    .incident-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      background: var(--secondary-background-color, #fafafa);
      border-left: 4px solid var(--divider-color, #e0e0e0);
      border-radius: 4px;
      text-decoration: none;
      color: inherit;
      transition: transform 0.15s ease, background 0.15s ease;
    }
    .incident-item:hover {
      background: var(--table-row-hover-color, #f0f4f8);
      transform: translateX(2px);
    }
    .incident-item.emergency {
      border-left-color: #d32f2f;
    }
    .incident-item.watch-act {
      border-left-color: #e65100;
    }
    .incident-item.advice {
      border-left-color: #fbc02d;
    }
    .incident-main {
      flex: 1;
      margin-right: 12px;
    }
    .incident-title {
      font-size: 0.9rem;
      font-weight: 600;
      line-height: 1.25;
    }
    .incident-sub {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      margin-top: 3px;
    }
    .incident-meta {
      text-align: right;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 4px;
    }
    .badge {
      font-size: 0.7rem;
      padding: 2px 8px;
      border-radius: 10px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-emergency {
      background: #ffebee;
      color: #c62828;
    }
    .badge-watch-act {
      background: #fff3e0;
      color: #ef6c00;
    }
    .badge-advice {
      background: #fffde7;
      color: #f57f17;
    }
    .badge-info {
      background: #e3f2fd;
      color: #1565c0;
    }
    .distance-tag {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--primary-color, #0288d1);
    }
    .footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 14px;
      padding-top: 10px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .btn-map {
      background: var(--primary-color, #03a9f4);
      color: #fff;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
      font-size: 0.85rem;
    }
    .btn-map:hover {
      filter: brightness(0.9);
    }
    .empty-state {
      padding: 24px 12px;
      text-align: center;
      color: var(--secondary-text-color, #757575);
      font-size: 0.9rem;
    }
  `;

  public setConfig(config: LovelaceCardConfig): void {
    this._config = {
      title: "Australian Disaster Watch",
      max_incidents: 10,
      show_map_button: true,
      ...config,
    };
  }

  public set hass(hass: HomeAssistant) {
    this._hass = hass;
  }

  public getCardSize(): number {
    return 6;
  }

  static getStubConfig(): LovelaceCardConfig {
    return {
      type: "custom:aus-disaster-card",
      title: "Australian Disaster Watch",
      max_incidents: 10,
      show_map_button: true,
    };
  }

  private _findEntity(prefix: string): any {
    if (!this._hass) return null;
    if (this._config?.entity && this._hass.states[this._config.entity]) {
      return this._hass.states[this._config.entity];
    }
    const matchingKey = Object.keys(this._hass.states).find((key) =>
      key.startsWith(prefix)
    );
    return matchingKey ? this._hass.states[matchingKey] : null;
  }

  private _getNearbyIncidents(): IncidentItem[] {
    if (!this._hass) return [];

    const incidents: IncidentItem[] = [];
    const geoPrefix = "geo_location.";

    // Look for geo_location entities added by the australian_disaster_watch integration
    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (
        entityId.startsWith(geoPrefix) &&
        stateObj.attributes &&
        (stateObj.attributes.source?.includes("Queensland") ||
          stateObj.attributes.source?.includes("Disaster") ||
          stateObj.attributes.source?.includes("NSW") ||
          stateObj.attributes.source?.includes("Vic") ||
          stateObj.attributes.source?.includes("Bureau") ||
          stateObj.attributes.source?.includes("australian_disaster_watch"))
      ) {
        incidents.push({
          id: entityId,
          title: stateObj.state || stateObj.attributes.title || "Emergency Incident",
          hazard_type: stateObj.attributes.hazard_type || "Other",
          warning_level: stateObj.attributes.warning_level || "Information",
          distance_km: stateObj.attributes.distance_km || stateObj.attributes.distance,
          location_name: stateObj.attributes.location_name,
          responsible_agency: stateObj.attributes.responsible_agency || stateObj.attributes.source,
          web_url: stateObj.attributes.web_url,
          status: stateObj.attributes.status,
          updated_at: stateObj.attributes.updated_at,
        });
      }
    }

    // Sort by distance ascending
    incidents.sort((a, b) => (a.distance_km ?? 9999) - (b.distance_km ?? 9999));
    return incidents;
  }

  override render() {
    if (!this._hass) {
      return html`<ha-card><div class="empty-state">Loading...</div></ha-card>`;
    }

    const warningSensor = this._findEntity("sensor.highest_warning_level");
    const countSensor = this._findEntity("sensor.active_hazards_count");
    const distanceSensor = this._findEntity("sensor.nearest_hazard_distance");

    const highestLevel = warningSensor?.state || "All Clear";
    const activeCount = countSensor ? parseInt(countSensor.state, 10) || 0 : 0;
    const nearestDist = distanceSensor?.state ? `${distanceSensor.state} km` : "None";

    let bannerClass = "banner-clear";
    let bannerText = "ALL CLEAR — NO ACTIVE THREATS";
    let bannerIcon = "🛡️";

    if (highestLevel === "Emergency Warning") {
      bannerClass = "banner-emergency";
      bannerText = "EMERGENCY WARNING IN REGION";
      bannerIcon = "🚨";
    } else if (highestLevel === "Watch and Act") {
      bannerClass = "banner-watch-and-act";
      bannerText = "WATCH AND ACT IN REGION";
      bannerIcon = "⚠️";
    } else if (highestLevel === "Advice") {
      bannerClass = "banner-advice";
      bannerText = "ADVICE LEVEL ACTIVE";
      bannerIcon = "ℹ️";
    }

    let allIncidents = this._getNearbyIncidents();

    // Filter incidents
    let filtered = allIncidents;
    if (this._filter === "fire") {
      filtered = allIncidents.filter((i) =>
        i.hazard_type.toLowerCase().includes("fire")
      );
    } else if (this._filter === "weather") {
      filtered = allIncidents.filter((i) =>
        ["flood", "storm", "cyclone"].some((k) =>
          i.hazard_type.toLowerCase().includes(k)
        )
      );
    } else if (this._filter === "road") {
      filtered = allIncidents.filter((i) =>
        i.hazard_type.toLowerCase().includes("road")
      );
    }

    const maxToShow = this._config?.max_incidents || 10;
    const displayed = filtered.slice(0, maxToShow);

    return html`
      <ha-card>
        <div class="header">
          <div class="title">
            <span>🇦🇺</span>
            <span>${this._config?.title || "Australian Disaster Watch"}</span>
          </div>
        </div>

        <div class="banner ${bannerClass}">
          <span>${bannerIcon} ${bannerText}</span>
          <span>${activeCount} active</span>
        </div>

        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-label">Nearest Hazard</span>
            <span class="stat-value">${nearestDist}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Active in Perimeter</span>
            <span class="stat-value">${activeCount}</span>
          </div>
        </div>

        <div class="filters">
          <div
            class="filter-chip ${this._filter === "all" ? "active" : ""}"
            @click=${() => (this._filter = "all")}
          >
            All Hazards (${allIncidents.length})
          </div>
          <div
            class="filter-chip ${this._filter === "fire" ? "active" : ""}"
            @click=${() => (this._filter = "fire")}
          >
            Fires
          </div>
          <div
            class="filter-chip ${this._filter === "weather" ? "active" : ""}"
            @click=${() => (this._filter = "weather")}
          >
            Weather / Flood
          </div>
          <div
            class="filter-chip ${this._filter === "road" ? "active" : ""}"
            @click=${() => (this._filter = "road")}
          >
            Roads
          </div>
        </div>

        <div class="incidents-list">
          ${displayed.length === 0
            ? html`<div class="empty-state">
                No active incidents found in this filter within the monitored radius.
              </div>`
            : displayed.map((inc) => {
                let badgeClass = "badge-info";
                let itemClass = "";
                if (inc.warning_level === "Emergency Warning") {
                  badgeClass = "badge-emergency";
                  itemClass = "emergency";
                } else if (inc.warning_level === "Watch and Act") {
                  badgeClass = "badge-watch-act";
                  itemClass = "watch-act";
                } else if (inc.warning_level === "Advice") {
                  badgeClass = "badge-advice";
                  itemClass = "advice";
                }

                return html`
                  <a
                    class="incident-item ${itemClass}"
                    href="${inc.web_url || "/map"}"
                    target="${inc.web_url ? "_blank" : "_self"}"
                    rel="noreferrer"
                  >
                    <div class="incident-main">
                      <div class="incident-title">${inc.title}</div>
                      <div class="incident-sub">
                        ${inc.hazard_type} • ${inc.responsible_agency || "Emergency Agency"}
                        ${inc.location_name ? `• ${inc.location_name}` : ""}
                      </div>
                    </div>
                    <div class="incident-meta">
                      <span class="badge ${badgeClass}">${inc.warning_level}</span>
                      ${inc.distance_km !== undefined
                        ? html`<span class="distance-tag">${inc.distance_km} km</span>`
                        : ""}
                    </div>
                  </a>
                `;
              })}
        </div>

        ${this._config?.show_map_button
          ? html`
              <div class="footer">
                <a class="btn-map" href="/map">
                  <span>🗺️</span>
                  <span>View Incidents on Map</span>
                </a>
              </div>
            `
          : ""}
      </ha-card>
    `;
  }
}

if (!customElements.get("aus-disaster-card")) {
  customElements.define("aus-disaster-card", AusDisasterCard);
}

// Register with Lovelace Card Picker window
(window as any).customCards = (window as any).customCards || [];
(window as any).customCards.push({
  type: "aus-disaster-card",
  name: "Australian Disaster Watch Card",
  description:
    "Real-time Australian Warning System disaster monitor and proximity hazard tracker.",
  preview: true,
  documentationURL:
    "https://github.com/ruaandeysel/ha-australian-disaster-watch",
});

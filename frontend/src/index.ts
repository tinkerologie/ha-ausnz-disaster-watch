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
  private _activeTab: string = "none";

  static override properties = {
    _config: { state: true },
    _hass: { state: true },
    _filter: { state: true },
    _activeTab: { state: true },
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
      margin-bottom: 14px;
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

    /* Top 4 Dashboard Metric Tiles */
    .dashboard-tiles {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-bottom: 14px;
    }
    @media (min-width: 480px) {
      .dashboard-tiles {
        grid-template-columns: repeat(4, 1fr);
      }
    }
    .dash-tile {
      border-radius: 8px;
      padding: 10px 12px;
      color: #ffffff;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.15s ease, filter 0.15s ease;
      min-height: 64px;
      user-select: none;
    }
    .dash-tile:hover {
      transform: translateY(-2px);
      filter: brightness(1.08);
    }
    .dash-tile.active {
      outline: 2px solid #ffffff;
      box-shadow: 0 0 8px rgba(0, 0, 0, 0.3);
    }
    .dash-tile-news {
      background: #c14619;
    }
    .dash-tile-power {
      background: #004a89;
    }
    .dash-tile-roads {
      background: #43525a;
    }
    .dash-tile-weather {
      background: #125b26;
    }
    .dash-tile-title {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .dash-tile-value {
      font-size: 1.35rem;
      font-weight: 700;
      margin-top: 4px;
      display: flex;
      align-items: baseline;
      gap: 4px;
    }
    .dash-tile-sub {
      font-size: 0.7rem;
      opacity: 0.9;
    }

    /* Quick Action Buttons (Relief, Cameras, Telemetry) */
    .quick-actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .action-btn {
      background: var(--secondary-background-color, #f0f0f0);
      color: var(--primary-text-color, #212121);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s ease;
      user-select: none;
    }
    .action-btn:hover {
      background: var(--primary-color, #0288d1);
      color: #fff;
      border-color: var(--primary-color, #0288d1);
    }
    .action-btn.active {
      background: var(--primary-color, #0288d1);
      color: #fff;
      border-color: var(--primary-color, #0288d1);
    }

    /* Drawer / Expanded Section */
    .drawer-content {
      background: var(--secondary-background-color, #fafafa);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 14px;
      animation: fadeIn 0.2s ease;
    }
    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(-4px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    .drawer-header {
      font-weight: 700;
      font-size: 0.9rem;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
      padding-bottom: 4px;
    }
    .drawer-close {
      cursor: pointer;
      font-size: 1rem;
      line-height: 1;
    }

    /* Outage & Road Item Cards */
    .detail-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      max-height: 260px;
      overflow-y: auto;
    }
    .detail-card {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 0.8rem;
    }
    .detail-card-title {
      font-weight: 600;
      margin-bottom: 3px;
    }
    .detail-card-meta {
      color: var(--secondary-text-color, #666);
      font-size: 0.72rem;
    }

    /* Telemetry Grid (Weather, Fire Danger, Air Quality) */
    .telemetry-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
      margin-top: 6px;
    }
    .telemetry-card {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 8px;
      text-align: center;
    }
    .telemetry-card-label {
      font-size: 0.7rem;
      color: var(--secondary-text-color, #666);
      text-transform: uppercase;
    }
    .telemetry-card-val {
      font-size: 1.1rem;
      font-weight: 700;
      margin-top: 2px;
    }
    .fdr-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 0.75rem;
      margin-top: 4px;
      color: #fff;
    }
    .fdr-moderate {
      background: #2e7d32;
    }
    .fdr-high {
      background: #f57f17;
    }
    .fdr-extreme {
      background: #e65100;
    }
    .fdr-catastrophic {
      background: #b71c1c;
    }

    /* Camera Grid */
    .camera-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 8px;
      max-height: 280px;
      overflow-y: auto;
    }
    .camera-card {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      overflow: hidden;
      font-size: 0.75rem;
    }
    .camera-img {
      width: 100%;
      height: 90px;
      object-fit: cover;
      background: #333;
      display: block;
    }
    .camera-label {
      padding: 4px 6px;
      font-weight: 600;
      text-overflow: ellipsis;
      overflow: hidden;
      white-space: nowrap;
    }

    /* Nearby Council Links */
    .council-links {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 6px;
    }
    .council-chip {
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 14px;
      padding: 4px 10px;
      font-size: 0.75rem;
      text-decoration: none;
      color: var(--primary-color, #0288d1);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .council-chip:hover {
      background: var(--secondary-background-color, #f0f0f0);
    }

    /* Filter Chips */
    .filters {
      display: flex;
      gap: 6px;
      margin-bottom: 10px;
      overflow-x: auto;
      padding-bottom: 2px;
    }
    .filter-chip {
      background: var(--secondary-background-color, #f0f0f0);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 16px;
      padding: 4px 10px;
      font-size: 0.75rem;
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

    /* Incidents List */
    .incidents-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 340px;
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
      font-size: 0.88rem;
      font-weight: 600;
      line-height: 1.25;
    }
    .incident-sub {
      font-size: 0.72rem;
      color: var(--secondary-text-color, #757575);
      margin-top: 3px;
    }
    .incident-meta {
      text-align: right;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 3px;
    }
    .badge {
      font-size: 0.68rem;
      padding: 2px 7px;
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
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--primary-color, #0288d1);
    }
    .footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 12px;
      padding-top: 8px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .btn-map {
      background: var(--primary-color, #03a9f4);
      color: #fff;
      border: none;
      padding: 7px 14px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
      font-size: 0.82rem;
    }
    .empty-state {
      padding: 16px 10px;
      text-align: center;
      color: var(--secondary-text-color, #757575);
      font-size: 0.85rem;
    }
  `;

  public setConfig(config: LovelaceCardConfig): void {
    this._config = {
      title: "Australia and New Zealand Disaster Watch",
      max_incidents: 10,
      show_map_button: true,
      ...config,
    };
  }

  public set hass(hass: HomeAssistant) {
    this._hass = hass;
  }

  public getCardSize(): number {
    return 7;
  }

  static getStubConfig(): LovelaceCardConfig {
    return {
      type: "custom:ausnz-disaster-card",
      title: "Australia and New Zealand Disaster Watch",
      max_incidents: 10,
      show_map_button: true,
    };
  }

  private _findEntity(suffix: string, allowSuffixFallback = true): any {
    if (!this._hass) return null;
    const entities = (this._hass as any).entities ?? {};

    // 1. Strict match with entity registry platform
    let matchingKey = Object.keys(this._hass.states).find(
      (key) =>
        key.startsWith("sensor.") &&
        key.endsWith(`_${suffix}`) &&
        entities[key]?.platform === "ausnz_disaster_watch"
    );

    // 2. Integration / attribution attribute match
    if (!matchingKey) {
      matchingKey = Object.keys(this._hass.states).find((key) => {
        if (!key.startsWith("sensor.") || !key.endsWith(`_${suffix}`)) return false;
        const stateObj = this._hass!.states[key];
        const attr = stateObj?.attributes?.attribution || "";
        return (
          attr.includes("Disaster Watch") ||
          attr.includes("Emergency Services") ||
          stateObj?.attributes?.integration === "ausnz_disaster_watch"
        );
      });
    }

    // 3. Sensor prefix fallback (any integration) — callers can opt out where a suffix is ambiguous
    if (!matchingKey && allowSuffixFallback) {
      matchingKey = Object.keys(this._hass.states).find(
        (key) => key.startsWith("sensor.") && key.endsWith(`_${suffix}`)
      );
    }

    return matchingKey ? this._hass.states[matchingKey] : null;
  }

  private _getNearbyIncidents(): IncidentItem[] {
    if (!this._hass) return [];

    const incidents: IncidentItem[] = [];
    const geoPrefix = "geo_location.";

    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (
        entityId.startsWith(geoPrefix) &&
        stateObj.attributes &&
        (stateObj.attributes.integration === "ausnz_disaster_watch" ||
          stateObj.attributes.integration === "australian_disaster_watch" ||
          stateObj.attributes.source?.includes("ausnz_disaster_watch") ||
          stateObj.attributes.source?.includes("australian_disaster_watch"))
      ) {
        incidents.push({
          id: entityId,
          title: stateObj.state || stateObj.attributes.title || "Emergency Incident",
          hazard_type: stateObj.attributes.hazard_type || "Other",
          warning_level: stateObj.attributes.warning_level || "Information",
          distance_km: stateObj.attributes.distance_km || stateObj.attributes.distance,
          location_name: stateObj.attributes.location_name,
          responsible_agency:
            stateObj.attributes.responsible_agency || stateObj.attributes.agency || stateObj.attributes.source,
          web_url: stateObj.attributes.web_url,
          status: stateObj.attributes.status,
          updated_at: stateObj.attributes.updated_at,
        });
      }
    }

    incidents.sort((a, b) => (a.distance_km ?? 9999) - (b.distance_km ?? 9999));
    return incidents;
  }

  private _toggleTab(tab: string): void {
    this._activeTab = this._activeTab === tab ? "none" : tab;
  }

  override render() {
    if (!this._hass) {
      return html`<ha-card><div class="empty-state">Loading...</div></ha-card>`;
    }

    // Retrieve state sensors
    const warningSensor = this._findEntity("highest_warning_level");
    const countSensor = this._findEntity("active_hazards_count");
    const outagesSensor = this._findEntity("power_outages_count");
    const roadsSensor = this._findEntity("road_closures_count");
    const weatherWarnSensor = this._findEntity("weather_warnings_count");
    const fireDangerSensor = this._findEntity("fire_danger_rating");
    const airQualitySensor = this._findEntity("air_quality");
    const weatherObsSensor =
      this._findEntity("local_weather_observation", false) || this._findEntity("primary_weather_observation");
    const reliefSensor = this._findEntity("relief_facilities_count");

    const highestLevel = warningSensor?.state || "All Clear";
    const activeCount = countSensor ? parseInt(countSensor.state, 10) || 0 : 0;
    const outagesCount = outagesSensor ? parseInt(outagesSensor.state, 10) || 0 : 0;
    const roadsCount = roadsSensor ? parseInt(roadsSensor.state, 10) || 0 : 0;
    const weatherWarnCount = weatherWarnSensor ? parseInt(weatherWarnSensor.state, 10) || 0 : 0;
    const reliefCount = reliefSensor ? parseInt(reliefSensor.state, 10) || 0 : 0;

    const customersAffected = outagesSensor?.attributes?.customers_affected || 0;
    const outagesList = outagesSensor?.attributes?.outages || [];
    const closuresList = roadsSensor?.attributes?.closures || [];
    const warningsList = weatherWarnSensor?.attributes?.warnings || [];
    const reliefList = reliefSensor?.attributes?.facilities || [];

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

    // Weather & Telemetry values
    const tempVal = weatherObsSensor?.state !== undefined ? `${weatherObsSensor.state}°C` : "--";
    const humidityVal = weatherObsSensor?.attributes?.relative_humidity ? `${weatherObsSensor.attributes.relative_humidity}%` : "--";
    const pressureVal = weatherObsSensor?.attributes?.pressure_hpa ? `${weatherObsSensor.attributes.pressure_hpa} hPa` : "--";
    const windVal = weatherObsSensor?.attributes?.wind_speed_avg_kph ? `${weatherObsSensor.attributes.wind_speed_avg_kph} km/h` : "--";
    const fdrVal = fireDangerSensor?.state && fireDangerSensor.state !== "unknown" && fireDangerSensor.state !== "unavailable" ? fireDangerSensor.state : "--";
    const aqVal = airQualitySensor?.state && airQualitySensor.state !== "unknown" && airQualitySensor.state !== "unavailable" ? airQualitySensor.state : "--";

    const newsList =
      weatherWarnSensor?.attributes?.emergency_news ||
      warningSensor?.attributes?.emergency_news ||
      [];
    const newsCount = newsList.length;

    const councilsList =
      weatherWarnSensor?.attributes?.nearby_councils ||
      warningSensor?.attributes?.nearby_councils ||
      [];

    const cameraEntities = Object.entries(this._hass.states)
      .filter(([entityId, stateObj]) => {
        if (!entityId.startsWith("camera.")) return false;
        const entities = (this._hass as any).entities ?? {};
        return (
          entities[entityId]?.platform === "ausnz_disaster_watch" ||
          entities[entityId]?.platform === "australian_disaster_watch" ||
          stateObj.attributes?.integration === "ausnz_disaster_watch" ||
          stateObj.attributes?.integration === "australian_disaster_watch" ||
          entityId.includes("disaster_watch")
        );
      })
      .map(([entityId, stateObj]) => ({
        entityId,
        name: stateObj.attributes.friendly_name || stateObj.attributes.name || entityId.replace("camera.", ""),
      }));

    return html`
      <ha-card>
        <div class="header">
          <div class="title">
            <span>🚨</span>
            <span>${this._config?.title || "Australia and New Zealand Disaster Watch"}</span>
          </div>
        </div>

        <div class="banner ${bannerClass}">
          <span>${bannerIcon} ${bannerText}</span>
          <span>${activeCount} active hazards</span>
        </div>

        <!-- 4 Top Metric Tiles (Emergency News, Power Outages, Road Conditions, Weather Warnings) -->
        <div class="dashboard-tiles">
          <div
            class="dash-tile dash-tile-news ${this._activeTab === "news" ? "active" : ""}"
            @click=${() => this._toggleTab("news")}
          >
            <div class="dash-tile-title">
              <span>📰</span>
              <span>Emergency News</span>
            </div>
            <div class="dash-tile-value">
              <span>${newsCount}</span>
              <span class="dash-tile-sub">Bulletins</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-power ${this._activeTab === "outages" ? "active" : ""}"
            @click=${() => this._toggleTab("outages")}
          >
            <div class="dash-tile-title">
              <span>⚡</span>
              <span>Power Outages</span>
            </div>
            <div class="dash-tile-value">
              <span>${outagesCount}</span>
              <span class="dash-tile-sub">(${customersAffected} affected)</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-roads ${this._activeTab === "roads" ? "active" : ""}"
            @click=${() => this._toggleTab("roads")}
          >
            <div class="dash-tile-title">
              <span>🚧</span>
              <span>Road Conditions</span>
            </div>
            <div class="dash-tile-value">
              <span>${roadsCount}</span>
              <span class="dash-tile-sub">Closures</span>
            </div>
          </div>

          <div
            class="dash-tile dash-tile-weather ${this._activeTab === "warnings" ? "active" : ""}"
            @click=${() => this._toggleTab("warnings")}
          >
            <div class="dash-tile-title">
              <span>⛈️</span>
              <span>Weather Warnings</span>
            </div>
            <div class="dash-tile-value">
              <span>${weatherWarnCount}</span>
              <span class="dash-tile-sub">BoM Alerts</span>
            </div>
          </div>
        </div>

        <!-- Quick Action Buttons -->
        <div class="quick-actions">
          <button
            class="action-btn ${this._activeTab === "telemetry" ? "active" : ""}"
            @click=${() => this._toggleTab("telemetry")}
          >
            <span>🌡️</span>
            <span>Conditions & AFDRS</span>
          </button>

          <button
            class="action-btn ${this._activeTab === "cameras" ? "active" : ""}"
            @click=${() => this._toggleTab("cameras")}
          >
            <span>📹</span>
            <span>Flood Cameras (${cameraEntities.length})</span>
          </button>

          <button
            class="action-btn ${this._activeTab === "relief" ? "active" : ""}"
            @click=${() => this._toggleTab("relief")}
          >
            <span>🏠</span>
            <span>Relief & Evac (${reliefCount})</span>
          </button>

          <button
            class="action-btn ${this._activeTab === "councils" ? "active" : ""}"
            @click=${() => this._toggleTab("councils")}
          >
            <span>🏛️</span>
            <span>Nearby Councils (${councilsList.length})</span>
          </button>
        </div>

        <!-- Expandable Drawer for Active Tab -->
        ${this._activeTab !== "none"
          ? html`
              <div class="drawer-content">
                ${this._activeTab === "news"
                  ? html`
                      <div class="drawer-header">
                        <span>📰 Emergency Bulletins & News (${newsCount})</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${newsList.length === 0
                          ? html`<div class="empty-state">No active emergency news or bulletins published.</div>`
                          : newsList.map(
                              (n: any) => html`
                                <div class="detail-card">
                                  <div class="detail-card-title">${n.title || "Disaster News"}</div>
                                  ${n.description ? html`<div class="detail-card-meta">${n.description}</div>` : ""}
                                  ${n.link ? html`<div class="detail-card-meta"><a href="${n.link}" target="_blank" rel="noreferrer" style="color:var(--primary-color);">Read official release →</a></div>` : ""}
                                </div>
                              `
                            )}
                      </div>
                    `
                  : ""}

                ${this._activeTab === "outages"
                  ? html`
                      <div class="drawer-header">
                        <span>⚡ Power Outages (${outagesCount} active — ${customersAffected} customers affected)</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${outagesList.length === 0
                          ? html`<div class="empty-state">No power outages reported in monitored area.</div>`
                          : outagesList.map(
                              (o: any) => html`
                                <div class="detail-card">
                                  <div class="detail-card-title">${o.suburb || "Local Suburb"} — ${o.cause}</div>
                                  <div class="detail-card-meta">
                                    Customers: ${o.customers_affected} • Estimated Restoration: ${o.restore_time || "Pending"}
                                  </div>
                                </div>
                              `
                            )}
                      </div>
                    `
                  : ""}

                ${this._activeTab === "roads"
                  ? html`
                      <div class="drawer-header">
                        <span>🚧 Road Conditions & Closures (${roadsCount})</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${closuresList.length === 0
                          ? html`<div class="empty-state">No road closures reported in monitored area.</div>`
                          : closuresList.map(
                              (c: any) => html`
                                <div class="detail-card">
                                  <div class="detail-card-title">${c.road} (${c.suburb || "Region"}) — ${c.status}</div>
                                  <div class="detail-card-meta">
                                    Reason: ${c.reason || "Hazard"} • Agency: ${c.source} ${c.advice ? `• Advice: ${c.advice}` : ""}
                                  </div>
                                </div>
                              `
                            )}
                      </div>
                    `
                  : ""}

                ${this._activeTab === "warnings"
                  ? html`
                      <div class="drawer-header">
                        <span>⛈️ Bureau of Meteorology Warnings (${weatherWarnCount})</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${warningsList.length === 0
                          ? html`<div class="empty-state">No weather warnings currently active.</div>`
                          : warningsList.map(
                              (w: any) => html`
                                <div class="detail-card">
                                  <div class="detail-card-title">
                                    <a href="${w.link || "#"}" target="_blank" rel="noreferrer" style="color:inherit;text-decoration:underline;">
                                      ${w.title}
                                    </a>
                                  </div>
                                  <div class="detail-card-meta">Districts: ${w.locations || "Forecast Area"}</div>
                                </div>
                              `
                            )}
                      </div>
                    `
                  : ""}

                ${this._activeTab === "telemetry"
                  ? html`
                      <div class="drawer-header">
                        <span>🌡️ Environmental Telemetry & Fire Danger</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      <div class="telemetry-grid">
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Air Temp</div>
                          <div class="telemetry-card-val">${tempVal}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Humidity</div>
                          <div class="telemetry-card-val">${humidityVal}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Pressure</div>
                          <div class="telemetry-card-val">${pressureVal}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Wind Speed</div>
                          <div class="telemetry-card-val">${windVal}</div>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Fire Danger (AFDRS)</div>
                          <span class="fdr-badge ${
                            fdrVal.toLowerCase().includes("catastrophic")
                              ? "fdr-catastrophic"
                              : fdrVal.toLowerCase().includes("extreme")
                              ? "fdr-extreme"
                              : fdrVal.toLowerCase().includes("high")
                              ? "fdr-high"
                              : "fdr-moderate"
                          }">${fdrVal}</span>
                        </div>
                        <div class="telemetry-card">
                          <div class="telemetry-card-label">Air Quality</div>
                          <div class="telemetry-card-val" style="color:#2e7d32;">${aqVal}</div>
                        </div>
                      </div>
                    `
                  : ""}

                ${this._activeTab === "cameras"
                  ? html`
                      <div class="drawer-header">
                        <span>📹 Live Flood & Traffic Webcams (${cameraEntities.length})</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      ${cameraEntities.length === 0
                        ? html`<div class="detail-list"><div class="empty-state">No live flood or traffic cameras available for this jurisdiction.</div></div>`
                        : html`
                            <div class="camera-grid">
                              ${cameraEntities.map(
                                (cam: any) => html`
                                  <div class="camera-card">
                                    <img
                                      class="camera-img"
                                      src="/api/camera_proxy/${cam.entityId}"
                                      alt="${cam.name}"
                                      loading="lazy"
                                    />
                                    <div class="camera-label">${cam.name}</div>
                                  </div>
                                `
                              )}
                            </div>
                          `}
                    `
                  : ""}

                ${this._activeTab === "relief"
                  ? html`
                      <div class="drawer-header">
                        <span>🏠 Disaster Relief Facilities</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      <div class="detail-list">
                        ${reliefList.length === 0
                          ? html`<div class="empty-state">No open relief facilities or evacuations required at this time.</div>`
                          : reliefList.map(
                              (f: any) => html`
                                <div class="detail-card">
                                  <div class="detail-card-title">${f.name} (${f.suburb || "Region"})</div>
                                  <div class="detail-card-meta">Address: ${f.address || "Council Depot"} • Status: ${f.status}</div>
                                </div>
                              `
                            )}
                      </div>
                    `
                  : ""}

                ${this._activeTab === "councils"
                  ? html`
                      <div class="drawer-header">
                        <span>🏛️ Connected Australian Disaster Dashboards (${councilsList.length})</span>
                        <span class="drawer-close" @click=${() => (this._activeTab = "none")}>✕</span>
                      </div>
                      ${councilsList.length === 0
                        ? html`<div class="detail-list"><div class="empty-state">No neighboring council disaster dashboards configured for this jurisdiction.</div></div>`
                        : html`
                            <div class="council-links">
                              ${councilsList.map(
                                (c: any) => html`
                                  <a class="council-chip" href="${c.url}" target="_blank" rel="noreferrer">
                                    <span>📍</span> ${c.name}
                                  </a>
                                `
                              )}
                            </div>
                          `}
                    `
                  : ""}
              </div>
            `
          : ""}

        <!-- Filter Chips for Incident List -->
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

        <!-- Incidents List -->
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

if (!customElements.get("ausnz-disaster-card")) {
  customElements.define("ausnz-disaster-card", AusDisasterCard);
}
if (!customElements.get("aus-disaster-card")) {
  customElements.define("aus-disaster-card", AusDisasterCard);
}

// Register with Lovelace Card Picker window
(window as any).customCards = (window as any).customCards || [];
if (
  !(window as any).customCards.some(
    (card: any) => card.type === "ausnz-disaster-card"
  )
) {
  (window as any).customCards.push({
    type: "ausnz-disaster-card",
    name: "Australia and New Zealand Disaster Watch Card",
    description:
      "Real-time Australia and New Zealand Warning System disaster monitor and proximity hazard tracker.",
    preview: true,
    documentationURL: "https://github.com/tinkerologie/ha-ausnz-disaster-watch",
  });
}
if (
  !(window as any).customCards.some(
    (card: any) => card.type === "aus-disaster-card"
  )
) {
  (window as any).customCards.push({
    type: "aus-disaster-card",
    name: "Australia and New Zealand Disaster Watch Card (Legacy Alias)",
    description:
      "Real-time Australia and New Zealand Warning System disaster monitor and proximity hazard tracker.",
    preview: false,
    documentationURL: "https://github.com/tinkerologie/ha-ausnz-disaster-watch",
  });
}

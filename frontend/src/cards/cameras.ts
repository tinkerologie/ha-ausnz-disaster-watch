import { css, html, type PropertyValues, type TemplateResult } from "lit";
import { cameraIdsFor, resolveDevice } from "../ha/entities";
import { isUnavailable, stringAttr } from "../ha/format";
import { t } from "../localize/localize";
import { empty, header } from "../components/render";
import type { BaseCardConfig, HomeAssistant, LovelaceConfigForm } from "../types";
import { areaSchema, assertPositiveInt, baseSchema, computeHelper, computeLabel, DisasterCard, stubConfig } from "./base";

export interface CamerasCardConfig extends BaseCardConfig {
  refresh_interval?: number;
}

export const DEFAULT_REFRESH_INTERVAL = 60;

/** Path HA signs for a snapshot; only ever used through `auth/sign_path`. */
const snapshotPath = (entityId: string) => `/api/camera_proxy/${entityId}`; // lint-modern-ignore camera-proxy: signed below
const MIN_REFRESH_INTERVAL = 10;

/**
 * Camera snapshot grid. Images use `entity_picture`, which carries the camera access
 * token (a bare camera proxy URL fails with 401, #26), and refresh only while visible.
 */
export class CamerasCard extends DisasterCard<CamerasCardConfig> {
  static override properties = {
    ...DisasterCard.properties,
    _tick: { state: true },
    _failed: { state: true },
    _signed: { state: true },
  };

  static override styles = [
    ...DisasterCard.styles,
    css`
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(calc(var(--ha-space-20) * 2), 1fr));
        gap: var(--ha-space-3);
      }
      .camera {
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1);
        min-width: 0;
        text-align: start;
      }
      .frame {
        position: relative;
        aspect-ratio: 16 / 9;
        overflow: hidden;
        border-radius: var(--ha-border-radius-lg);
        background-color: var(--ha-color-fill-neutral-quiet-resting);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--secondary-text-color);
      }
      .frame img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
      .placeholder {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--ha-space-1);
        font-size: var(--ha-font-size-s);
      }
      .name {
        font-size: var(--ha-font-size-s);
        font-weight: var(--ha-font-weight-medium);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .camera:hover .frame {
        background-color: var(--ha-color-fill-neutral-quiet-hover);
      }
    `,
  ];

  protected declare _tick: number;
  protected declare _failed: Set<string>;
  /** Signed snapshot URLs (entity_id@tick) for cameras that have no entity_picture yet. */
  protected declare _signed: Record<string, string>;
  private readonly _signing = new Set<string>();
  protected readonly titleKey = "cameras.title" as const;
  static override readonly defaultArea = "council" as const;
  private _timer?: ReturnType<typeof setInterval>;
  private _observer?: IntersectionObserver;
  private _visible = false;
  private readonly _onVisibility = () => this.updateTimer();

  constructor() {
    super();
    this._tick = 0;
    this._failed = new Set();
    this._signed = {};
  }

  protected override extraEntityIds(hass: HomeAssistant): string[] {
    return cameraIdsFor(hass, resolveDevice(hass, this.config?.device));
  }

  static override validateConfig(config: CamerasCardConfig): void {
    super.validateConfig(config);
    assertPositiveInt(config as unknown as Record<string, unknown>, "refresh_interval", MIN_REFRESH_INTERVAL, 3600);
  }

  static getConfigForm(): LovelaceConfigForm {
    return {
      schema: [
        ...baseSchema(),
        areaSchema(this.defaultArea),
        {
          name: "refresh_interval",
          selector: {
            number: { min: MIN_REFRESH_INTERVAL, max: 3600, step: 5, mode: "box", unit_of_measurement: "s" },
          },
        },
      ],
      computeLabel,
      computeHelper,
      assertConfig: (c) => this.validateConfig(c),
    };
  }

  static getStubConfig(hass: HomeAssistant) {
    return stubConfig(hass);
  }

  override getCardSize(): number {
    return 4;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    document.addEventListener("visibilitychange", this._onVisibility);
    if ("IntersectionObserver" in window) {
      this._observer = new IntersectionObserver((entries) => {
        this._visible = entries.some((e) => e.isIntersecting);
        this.updateTimer();
      });
      this._observer.observe(this);
    } else {
      this._visible = true;
      this.updateTimer();
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    document.removeEventListener("visibilitychange", this._onVisibility);
    this._observer?.disconnect();
    this._observer = undefined;
    this._visible = false;
    this.updateTimer();
  }

  protected override updated(changed: PropertyValues<this>): void {
    super.updated(changed);
    this.signMissing();
    if (changed.has("_config" as keyof CamerasCard) && this._timer) {
      // Restart with the new interval.
      clearInterval(this._timer);
      this._timer = undefined;
      this.updateTimer();
    }
  }

  /** Run the refresh timer only while the card is on screen and the page is visible. */
  private updateTimer(): void {
    const run = this._visible && document.visibilityState === "visible" && this.isConnected;
    if (run && !this._timer) {
      const seconds = this._config?.refresh_interval ?? DEFAULT_REFRESH_INTERVAL;
      this._timer = setInterval(() => {
        this._failed = new Set();
        this._tick += 1;
      }, seconds * 1000);
    } else if (!run && this._timer) {
      clearInterval(this._timer);
      this._timer = undefined;
    }
  }

  /**
   * The integration publishes `entity_picture` only once a snapshot was fetched, so for
   * the others ask Home Assistant for a short-lived signed snapshot URL, the way its own
   * picture cards do (`auth/sign_path`).
   */
  private signMissing(): void {
    const hass = this.hass;
    if (!hass) return;
    for (const id of this.cameraIds(hass)) {
      const s = hass.states[id];
      if (!s || isUnavailable(s) || stringAttr(s.attributes.entity_picture)) continue;
      const key = `${id}@${this._tick}`;
      if (this._signed[key] || this._signing.has(key)) continue;
      this._signing.add(key);
      hass.connection
        .sendMessagePromise<{ path: string }>({ type: "auth/sign_path", path: snapshotPath(id), expires: 300 })
        .then((result) => {
          if (result?.path) this._signed = { ...this.prune(), [key]: result.path };
        })
        .catch(() => undefined)
        .finally(() => this._signing.delete(key));
    }
  }

  /** The entry's cameras the card shows: those in the council area unless asked for the radius (#94). */
  private cameraIds(hass: HomeAssistant): string[] {
    const area = this.areaFilter(hass);
    return cameraIdsFor(hass, this.deviceId).filter((id) => area.keep(hass.states[id]?.attributes.in_council_area));
  }

  private prune(): Record<string, string> {
    return Object.fromEntries(Object.entries(this._signed).filter(([k]) => k.endsWith(`@${this._tick}`)));
  }

  private imageUrl(picture: string): string {
    if (!this._tick) return picture;
    return `${picture}${picture.includes("?") ? "&" : "?"}t=${this._tick}`;
  }

  protected renderBody(hass: HomeAssistant, _config: CamerasCardConfig): TemplateResult {
    const ids = this.cameraIds(hass);
    const area = this.areaFilter(hass);
    return html`${header({
        title: this.cardTitle(),
        icon: "mdi:cctv",
        count: ids.length ? String(ids.length) : undefined,
        subtitle: area.council?.name,
      })}
      <div class="content">
        ${this.areaHint(hass, area)}
        ${
          ids.length
            ? html`<div class="grid" role="list">
                ${ids.map((id) => {
                  const s = hass.states[id];
                  // The registry name is the camera's own name, without the device prefix.
                  const name = stringAttr(hass.entities[id]?.name) ?? stringAttr(s?.attributes.friendly_name) ?? id;
                  const picture = isUnavailable(s) ? undefined : stringAttr(s?.attributes.entity_picture);
                  const src = picture ? this.imageUrl(picture) : this._signed[`${id}@${this._tick}`];
                  const showImage = src && !this._failed.has(src);
                  return html`<div role="listitem">
                    <button class="plain camera" aria-label=${`${name}. ${t(hass, "action.details")}`} @click=${() => this.moreInfo(id)}>
                      <span class="frame">
                        ${
                          showImage
                            ? html`<img
                                src=${src}
                                alt=${name}
                                loading="lazy"
                                @error=${() => (this._failed = new Set([...this._failed, src]))}
                              />`
                            : html`<span class="placeholder">
                                <ha-icon icon="mdi:image-off-outline" aria-hidden="true"></ha-icon>
                                <span>${t(hass, "cameras.no_image")}</span>
                              </span>`
                        }
                      </span>
                      <span class="name">${name}</span>
                    </button>
                  </div>`;
                })}
              </div>`
            : empty("mdi:cctv-off", t(hass, "cameras.empty"))
        }
      </div>`;
  }
}

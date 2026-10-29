var e=`ausnz_disaster_watch`,t=`https://github.com/tinkerologie/ha-ausnz-disaster-watch#dashboard-cards`,n={emergencyWarningNearby:`emergency_warning_nearby`,activeHazardsNearby:`active_hazards_nearby`,powerOutageActive:`power_outage_active`,roadClosureNearby:`road_closure_nearby`,nearestHazardDistance:`nearest_hazard_distance`,activeHazardsCount:`active_hazards_count`,highestWarningLevel:`highest_warning_level`,nearestHazardTitle:`nearest_hazard_title`,powerOutagesCount:`power_outages_count`,powerOutagesCustomersAffected:`power_outages_customers_affected`,roadClosuresCount:`road_closures_count`,weatherWarningsCount:`weather_warnings_count`,fireDangerRating:`fire_danger_rating`,airQualityRating:`air_quality_rating`,primaryWeatherObservation:`primary_weather_observation`,reliefFacilitiesCount:`relief_facilities_count`,regionalDisasterAlerts:`regional_disaster_alerts`},r={status:`ausnz-disaster-status-card`,incidents:`ausnz-disaster-incidents-card`,warnings:`ausnz-disaster-warnings-card`,fire_danger:`ausnz-disaster-fire-danger-card`,outages:`ausnz-disaster-outages-card`,roads:`ausnz-disaster-roads-card`,conditions:`ausnz-disaster-conditions-card`,relief:`ausnz-disaster-relief-card`,cameras:`ausnz-disaster-cameras-card`,map:`ausnz-disaster-map-card`},i=`ausnz-disaster-card`,a=[`status`,`incidents`,`warnings`,`fire_danger`,`roads`,`outages`],o=Object.keys(r),s={"card.status.name":`Disaster Watch status`,"card.status.description":`Headline warning level, hazard count, nearest hazard and active alerts.`,"card.incidents.name":`Disaster Watch incidents`,"card.incidents.description":`Incidents nearest first, with category filters and Australian Warning System levels.`,"card.warnings.name":`Disaster Watch warnings`,"card.warnings.description":`Weather warnings and emergency news.`,"card.fire_danger.name":`Disaster Watch fire danger`,"card.fire_danger.description":`Fire danger rating on the AFDRS scale, district and total fire ban.`,"card.outages.name":`Disaster Watch power outages`,"card.outages.description":`Power outages and customers affected.`,"card.roads.name":`Disaster Watch roads`,"card.roads.description":`Road closures and hazards.`,"card.conditions.name":`Disaster Watch conditions`,"card.conditions.description":`Local weather observation and air quality.`,"card.relief.name":`Disaster Watch relief`,"card.relief.description":`Evacuation centres, places of refuge, sandbag stations and council dashboards.`,"card.cameras.name":`Disaster Watch cameras`,"card.cameras.description":`Flood and traffic camera snapshots.`,"card.map.name":`Disaster Watch map`,"card.map.description":`Map of incidents with animated rain radar, optional satellite imagery and cyclone tracks.`,"card.all.name":`Disaster Watch`,"card.all.description":`All-in-one card: a configurable stack of the Disaster Watch cards.`,"state.not_set_up":`Set up the Australia and New Zealand Disaster Watch integration to use this card.`,"state.device_missing":`The selected Disaster Watch device was not found. Choose another device in the card editor.`,"state.unavailable":`Data is unavailable right now.`,"state.entity_missing":`This Disaster Watch entity is missing or disabled.`,"action.details":`Show details`,"action.open_link":`Open source page`,"action.show_all":`Show all {count}`,"action.show_less":`Show less`,"status.all_clear":`All clear`,"status.unavailable":`Status unavailable`,"status.level.emergency":`Emergency Warning`,"status.level.watch_and_act":`Watch and Act`,"status.level.advice":`Advice`,"status.level.information":`Information`,"status.level.unknown":`Level unknown`,"status.hazards":`{count} hazards nearby`,"status.hazard":`1 hazard nearby`,"status.no_hazards":`No hazards nearby`,"status.hazards_council":`{count} hazards in {name}`,"status.hazard_council":`1 hazard in {name}`,"status.no_hazards_council":`No hazards in {name}`,"status.nearest":`nearest {distance}`,"status.chip.emergency_warning_nearby":`Emergency warning`,"status.chip.active_hazards_nearby":`Hazards nearby`,"status.chip.power_outage_active":`Power outage`,"status.chip.road_closure_nearby":`Road closure`,"status.alerts":`Active alerts`,"incidents.title":`Incidents`,"incidents.empty":`No incidents nearby.`,"incidents.empty_filtered":`No incidents in this category.`,"incidents.filters":`Incident filters`,"incidents.category.all":`All`,"incidents.category.fire":`Fire`,"incidents.category.flood_storm":`Flood & storm`,"incidents.category.geological":`Geological`,"incidents.category.roads":`Roads`,"incidents.category.other":`Other`,"incidents.planned_burns":`Planned burns`,"incidents.planned_burn":`Planned burn`,"incidents.updated":`updated {time}`,"incidents.nearest_camera":`Nearest camera: {name}`,"warnings.title":`Warnings`,"warnings.tab.warnings":`Warnings ({count})`,"warnings.tab.news":`News ({count})`,"warnings.views":`Warnings or news`,"warnings.empty":`No weather warnings.`,"warnings.news_empty":`No emergency news.`,"fire.title":`Fire danger`,"fire.rating.moderate":`Moderate`,"fire.rating.high":`High`,"fire.rating.extreme":`Extreme`,"fire.rating.catastrophic":`Catastrophic`,"fire.rating.no_rating":`No rating`,"fire.scale":`Fire danger rating scale`,"fire.current":`Current rating`,"fire.forecast_for":`Forecast for {day}`,"fire.total_fire_ban":`Total fire ban`,"fire.no_total_fire_ban":`No total fire ban`,"fire.district":`{district} district`,"outages.title":`Power outages`,"outages.count":`{count} outages`,"outages.count_one":`{count} outage`,"outages.customers_affected":`{count} customers affected`,"outages.customers_affected_one":`{count} customer affected`,"outages.empty":`No power outages reported.`,"outages.customers":`{count} customers`,"outages.customers_one":`{count} customer`,"outages.restore":`Restore {time}`,"roads.title":`Roads`,"roads.empty":`No road closures or hazards.`,"conditions.title":`Conditions`,"conditions.weather":`Weather`,"conditions.air_quality":`Air quality`,"conditions.temperature":`Temperature`,"conditions.feels_like":`Feels like`,"conditions.humidity":`Humidity`,"conditions.wind":`Wind`,"conditions.wind_from":`Wind from {direction}`,"conditions.gust":`Gust`,"conditions.pressure":`Pressure`,"conditions.rain":`Rain since 9 am`,"conditions.station":`Station: {name}`,"conditions.no_weather":`No weather observation.`,"conditions.no_air_quality":`No air quality reading.`,"conditions.aq.good":`Good`,"conditions.aq.fair":`Fair`,"conditions.aq.poor":`Poor`,"conditions.aq.very_poor":`Very poor`,"conditions.aq.extremely_poor":`Extremely poor`,"conditions.aq.unknown":`Unknown`,"relief.title":`Relief`,"relief.empty":`No relief facilities open nearby.`,"relief.group.evacuation_centre":`Evacuation centres`,"relief.group.place_of_refuge":`Places of refuge`,"relief.group.sandbag_station":`Sandbag stations`,"relief.group.other":`Other facilities`,"area.fallback":`Your council's boundary is not known yet, so everything within the radius is shown.`,"relief.own_council":`Council dashboard`,"relief.councils":`Nearby council dashboards`,"relief.open":`Open`,"relief.closed":`Closed`,"cameras.title":`Cameras`,"cameras.empty":`No cameras for this location.`,"cameras.no_image":`No image yet`,"map.title":`Map`,"map.label":`Map of incidents near {name}`,"map.home":`Home`,"map.play":`Play radar animation`,"map.pause":`Pause radar animation`,"map.radar_at":`Radar {time}`,"map.radar_unavailable":`Rain radar is unavailable right now.`,"map.radar_off":`Radar off`,"map.play_satellite":`Play satellite animation`,"map.pause_satellite":`Pause satellite animation`,"map.satellite_at":`Satellite {time}`,"map.satellite_unavailable":`Satellite imagery is unavailable right now.`,"map.layers":`Map layers`,"map.layer.himawari_visible":`Himawari visible`,"map.layer.himawari_ir":`Himawari infrared`,"map.layer.viirs_truecolor":`VIIRS true colour`,"map.viirs_days":`VIIRS image date`,"map.cyclones":`Cyclone tracks`,"map.cyclones_unavailable":`Cyclone tracks are unavailable right now.`,"map.cyclone_legend":`GDACS model estimate — follow BoM / MetService warnings.`,"editor.device":`Disaster Watch location`,"editor.device_helper":`The integration entry (location) this card shows. Defaults to the first one.`,"editor.title":`Title`,"editor.title_helper":`Leave empty for the default title.`,"editor.max_items":`Maximum items`,"editor.max_items_helper":`Rows shown before a Show all button.`,"editor.show_planned_burns":`Show planned burns`,"editor.show_planned_burns_helper":`Planned burns only reach the card when the integration's 'Exclude hazard reduction burns' option is off.`,"editor.show_nearby_councils":`Show nearby councils`,"editor.show_nearby_councils_helper":`Also link to the disaster dashboards of neighbouring councils. Off: only your own council's dashboard is shown.`,"editor.area":`Area`,"editor.area_helper":`Council: only what is in your council area (the boundary of the council your location is in). Radius: everything within the integration's radius.`,"editor.area.council":`My council`,"editor.area.radius":`Radius`,"editor.categories":`Categories`,"editor.categories_helper":`Incident categories to show. Leave empty for all.`,"editor.refresh_interval":`Refresh interval`,"editor.refresh_interval_helper":`Seconds between snapshot refreshes while the card is visible.`,"editor.zoom":`Zoom`,"editor.zoom_helper":`Initial zoom. Leave empty to fit all incidents.`,"editor.radar":`Rain radar`,"editor.radar_helper":`Animated RainViewer radar (free for personal use, attribution shown on the map).`,"editor.radar_opacity":`Radar opacity`,"editor.satellite_layer":`Satellite layer`,"editor.satellite_layer_helper":`Himawari clouds (every 10 minutes; visible is daytime only, infrared day and night) or the daily VIIRS true colour image (smoke, burn scars, flood extent). Imagery from NASA GIBS.`,"editor.satellite_layer.none":`None`,"editor.show_cyclone_tracks":`Cyclone tracks`,"editor.show_cyclone_tracks_helper":`Draw GDACS forecast tracks and wind areas of current cyclones listed by the Regional Disaster Alerts sensor (turn on 'Regional disaster alerts (GDACS)' in the integration options). Model estimates only: follow BoM and MetService warnings.`,"editor.cards":`Sections`,"editor.cards_helper":`Cards to stack, in order.`},c={en:s};function l(e){let t=e?.locale?.language||e?.language||`en`;if(c[t])return{lang:t,strings:c[t]};let n=t.split(`-`)[0]??`en`;return c[n]?{lang:n,strings:c[n]}:{lang:`en`,strings:s}}function u(e,t){let n=l(e);return n.strings[t]===void 0?{lang:`en`,strings:s,template:s[t]}:{...n,template:n.strings[t]}}function d(e,t){return t?e.replace(/\{(\w+)\}/g,(e,n)=>n in t?String(t[n]):e):e}function f(e,t,n){return d(u(e,t).template??t,n)}function p(e,t){try{return new Intl.PluralRules(e).select(t)}catch{return t===1?`one`:`other`}}function m(e,t,n,r=String(n)){let{lang:i,strings:a,template:o}=u(e,t),s=a[`${t}_one`];return d(p(i,n)===`one`&&s!==void 0?s:o??t,{count:r})}var h=globalThis,g=h.ShadowRoot&&(h.ShadyCSS===void 0||h.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,_=Symbol(),ee=new WeakMap,v=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==_)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(g&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=ee.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&ee.set(t,e))}return e}toString(){return this.cssText}},te=e=>new v(typeof e==`string`?e:e+``,void 0,_),y=(e,...t)=>new v(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,_),ne=(e,t)=>{if(g)e.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let n of t){let t=document.createElement(`style`),r=h.litNonce;r!==void 0&&t.setAttribute(`nonce`,r),t.textContent=n.cssText,e.appendChild(t)}},re=g?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return te(t)})(e):e,{is:ie,defineProperty:ae,getOwnPropertyDescriptor:oe,getOwnPropertyNames:se,getOwnPropertySymbols:ce,getPrototypeOf:le}=Object,ue=globalThis,de=ue.trustedTypes,fe=de?de.emptyScript:``,pe=ue.reactiveElementPolyfillSupport,b=(e,t)=>e,me={toAttribute(e,t){switch(t){case Boolean:e=e?fe:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},he=(e,t)=>!ie(e,t),ge={attribute:!0,type:String,converter:me,reflect:!1,useDefault:!1,hasChanged:he};Symbol.metadata??=Symbol(`metadata`),ue.litPropertyMetadata??=new WeakMap;var x=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ge){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&ae(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=oe(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ge}static _$Ei(){if(this.hasOwnProperty(b(`elementProperties`)))return;let e=le(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(b(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(b(`properties`))){let e=this.properties,t=[...se(e),...ce(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(re(e))}else e!==void 0&&t.push(re(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ne(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?me:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?me:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??he)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};x.elementStyles=[],x.shadowRootOptions={mode:`open`},x[b(`elementProperties`)]=new Map,x[b(`finalized`)]=new Map,pe?.({ReactiveElement:x}),(ue.reactiveElementVersions??=[]).push(`2.1.2`);var _e=globalThis,ve=e=>e,ye=_e.trustedTypes,be=ye?ye.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,xe=`$lit$`,S=`lit$${Math.random().toFixed(9).slice(2)}$`,Se=`?`+S,Ce=`<${Se}>`,C=document,we=()=>C.createComment(``),Te=e=>e===null||typeof e!=`object`&&typeof e!=`function`,Ee=Array.isArray,De=e=>Ee(e)||typeof e?.[Symbol.iterator]==`function`,Oe=`[ 	
\f\r]`,w=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ke=/-->/g,Ae=/>/g,T=RegExp(`>|${Oe}(?:([^\\s"'>=/]+)(${Oe}*=${Oe}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),je=/'/g,Me=/"/g,Ne=/^(?:script|style|textarea|title)$/i,E=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),D=Symbol.for(`lit-noChange`),O=Symbol.for(`lit-nothing`),Pe=new WeakMap,k=C.createTreeWalker(C,129);function Fe(e,t){if(!Ee(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return be===void 0?t:be.createHTML(t)}var Ie=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=w;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===w?c[1]===`!--`?o=ke:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=T):(Ne.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=T):o=Ae:o===T?c[0]===`>`?(o=i??w,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?T:c[3]===`"`?Me:je):o===Me||o===je?o=T:o===ke||o===Ae?o=w:(o=T,i=void 0);let d=o===T&&e[t+1].startsWith(`/>`)?` `:``;a+=o===w?n+Ce:l>=0?(r.push(s),n.slice(0,l)+xe+n.slice(l)+S+d):n+S+(l===-2?t:d)}return[Fe(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},Le=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=Ie(t,n);if(this.el=e.createElement(l,r),k.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=k.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(xe)){let t=u[o++],n=i.getAttribute(e).split(S),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?Ve:r[1]===`?`?He:r[1]===`@`?Ue:Be}),i.removeAttribute(e)}else e.startsWith(S)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(Ne.test(i.tagName)){let e=i.textContent.split(S),t=e.length-1;if(t>0){i.textContent=ye?ye.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],we()),k.nextNode(),c.push({type:2,index:++a});i.append(e[t],we())}}}else if(i.nodeType===8){if(i.data===Se)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(S,e+1))!==-1;)c.push({type:7,index:a}),e+=S.length-1}}a++}}static createElement(e,t){let n=C.createElement(`template`);return n.innerHTML=e,n}};function A(e,t,n=e,r){if(t===D)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=Te(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=A(e,i._$AS(e,t.values),i,r)),t}var Re=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??C).importNode(t,!0);k.currentNode=r;let i=k.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new ze(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new We(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=k.nextNode(),a++)}return k.currentNode=C,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},ze=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=O,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=A(this,e,t),Te(e)?e===O||e==null||e===``?(this._$AH!==O&&this._$AR(),this._$AH=O):e!==this._$AH&&e!==D&&this._(e):e._$litType$===void 0?e.nodeType===void 0?De(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==O&&Te(this._$AH)?this._$AA.nextSibling.data=e:this.T(C.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=Le.createElement(Fe(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new Re(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=Pe.get(e.strings);return t===void 0&&Pe.set(e.strings,t=new Le(e)),t}k(t){Ee(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(we()),this.O(we()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=ve(e).nextSibling;ve(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},Be=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=O,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=O}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=A(this,e,t,0),a=!Te(e)||e!==this._$AH&&e!==D,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=A(this,r[n+o],t,o),s===D&&(s=this._$AH[o]),a||=!Te(s)||s!==this._$AH[o],s===O?e=O:e!==O&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===O?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},Ve=class extends Be{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===O?void 0:e}},He=class extends Be{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==O)}},Ue=class extends Be{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=A(this,e,t,0)??O)===D)return;let n=this._$AH,r=e===O&&n!==O||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==O&&(n===O||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},We=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){A(this,e)}},Ge=_e.litHtmlPolyfillSupport;Ge?.(Le,ze),(_e.litHtmlVersions??=[]).push(`3.3.3`);var Ke=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new ze(t.insertBefore(we(),e),e,void 0,n??{})}return i._$AI(e),i},qe=globalThis,j=class extends x{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Ke(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return D}};j._$litElement$=!0,j.finalized=!0,qe.litElementHydrateSupport?.({LitElement:j});var Je=qe.litElementPolyfillSupport;Je?.({LitElement:j}),(qe.litElementVersions??=[]).push(`4.2.2`);var Ye={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Xe=e=>(...t)=>({_$litDirective$:e,values:t}),Ze=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},Qe=`important`,$e=` !`+Qe,et=Xe(class extends Ze{constructor(e){if(super(e),e.type!==Ye.ATTRIBUTE||e.name!==`style`||e.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(e){return Object.keys(e).reduce((t,n)=>{let r=e[n];return r==null?t:t+`${n=n.includes(`-`)?n:n.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,`-$&`).toLowerCase()}:${r};`},``)}update(e,[t]){let{style:n}=e.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let e of this.ft)t[e]??(this.ft.delete(e),e.includes(`-`)?n.removeProperty(e):n[e]=null);for(let e in t){let r=t[e];if(r!=null){this.ft.add(e);let t=typeof r==`string`&&r.endsWith($e);e.includes(`-`)||t?n.setProperty(e,t?r.slice(0,-11):r,t?Qe:``):n[e]=r}}return D}}),tt=new Set([`unavailable`,`unknown`]);function M(e){return!e||tt.has(e.state)}function nt(e){return e.locale?.language||e.language||`en`}function rt(e){return e.locale?.time_zone===`server`?e.config?.time_zone:void 0}function it(e,t,n=!1){let r=e.states[t],i=r&&e.formatEntityName?.(r,n?{type:`entity`}:void 0);if(typeof i==`string`&&i.trim())return i;let a=n?e.entities[t]?.name:void 0,o=r?.attributes.friendly_name;return(a||typeof o==`string`&&o||t).trim()}function at(e,t){if(e.formatEntityState)return e.formatEntityState(t);let n=t.attributes.unit_of_measurement;return n?`${t.state} ${n}`:t.state}function ot(e,t,n,r){let i=r===void 0?t.attributes[n]:r;return e.formatEntityAttributeValue?e.formatEntityAttributeValue(t,n,i):typeof i==`number`?N(e,i):String(i??``)}function N(e,t,n){try{return new Intl.NumberFormat(nt(e),n).format(t)}catch{return String(t)}}function P(e,t){if(t!=null&&Number.isFinite(t))return`${N(e,t,{maximumFractionDigits:+(t<10)})} km`}function st(e){if(typeof e!=`string`&&typeof e!=`number`)return;let t=typeof e==`string`?/^\/Date\((-?\d+)(?:[+-]\d{4})?\)\/$/.exec(e.trim()):null;if(t)return new Date(Number(t[1]));let n=new Date(e);return Number.isNaN(n.getTime())?void 0:n}var ct=[[`year`,31536e3],[`month`,2592e3],[`week`,604800],[`day`,86400],[`hour`,3600],[`minute`,60],[`second`,1]];function lt(e,t,n=Date.now()){let r=st(t);if(!r)return;let i=Math.round((r.getTime()-n)/1e3),a=new Intl.RelativeTimeFormat(nt(e),{numeric:`auto`});for(let[e,t]of ct)if(Math.abs(i)>=t||e===`second`)return a.format(Math.round(i/t),e)}function ut(e,t,n={dateStyle:`medium`,timeStyle:`short`}){let r=st(t);if(r)try{return new Intl.DateTimeFormat(nt(e),{...n,timeZone:rt(e)}).format(r)}catch{return r.toISOString()}}function dt(e){if(typeof e!=`string`||!e.trim())return;let t;try{t=new URL(e.trim())}catch{return}return t.protocol===`http:`||t.protocol===`https:`?t.href:void 0}function F(e){if(typeof e==`number`)return Number.isFinite(e)?e:void 0;if(typeof e==`string`&&e.trim()!==``){let t=Number(e);return Number.isFinite(t)?t:void 0}}function I(e){return typeof e==`string`&&e.trim()?e.trim():void 0}function L(e){return Array.isArray(e)?e.filter(e=>e&&typeof e==`object`):[]}function ft(e){return`var(--${e}-color)`}var pt=e=>et({"--tone":ft(e)});function mt(e,t,n=!1){return E`<span class="bubble ${n?`large`:``}" style=${pt(t)} aria-hidden="true">
    <ha-icon .icon=${e}></ha-icon>
  </span>`}function R(e,t,n){return E`<span class="badge" style=${pt(t)}>
    ${n?E`<ha-icon .icon=${n} aria-hidden="true"></ha-icon>`:O}<span>${e}</span>
  </span>`}function z(e,t){return E`<div class="empty"><ha-icon .icon=${e} aria-hidden="true"></ha-icon><span>${t}</span></div>`}function B(e,t){return E`<ha-alert alert-type=${e}>${t}</ha-alert>`}function V(e){return E`<div class="header">
    <ha-icon .icon=${e.icon} aria-hidden="true"></ha-icon>
    <div class="heading">
      <h2 class="title">${e.title}${e.count?E` <span class="count">${e.count}</span>`:O}</h2>
      ${e.subtitle?E`<span class="subtitle">${e.subtitle}</span>`:O}
    </div>
    ${e.onDetails?E`<div class="actions">
            <ha-icon-button .label=${e.detailsLabel??``} @click=${e.onDetails}>
              <ha-icon icon="mdi:information-outline"></ha-icon>
            </ha-icon-button>
          </div>`:O}
  </div>`}function H(e){let t=E`<span slot="start">${mt(e.icon,e.tone)}</span>
    <span slot="headline" class="headline">${e.headline}</span>
    ${e.badge?E`<span slot="supporting-text" class="row-badge">${e.badge}</span>`:O}
    ${e.supporting?E`<span slot="supporting-text" class="supporting">${e.supporting}</span>`:O}
    ${e.trailing?E`<span slot="end" class="trailing">${e.trailing}</span>`:O}`;return E`<div class="row" role="listitem">
    ${e.onActivate?E`<ha-list-item-button class="item" role="button" @click=${e.onActivate}
            >${t}</ha-list-item-button
          >`:E`<ha-list-item-base class="item" role="none">${t}</ha-list-item-base>`}
    ${e.link?E`<ha-icon-button
            class="link"
            .label=${e.linkLabel??``}
            .href=${e.link}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ha-icon icon="mdi:open-in-new"></ha-icon>
          </ha-icon-button>`:O}
    ${e.actions??O}
  </div>`}function U(e,t){return E`<ha-list-base class="list" aria-label=${t??O}>${e}</ha-list-base>`}function ht(e,t,n,r){return E`<ha-button
    class="more"
    appearance="plain"
    size="s"
    aria-expanded=${t?`true`:`false`}
    @click=${r}
    >${t?f(e,`action.show_less`):f(e,`action.show_all`,{count:N(e,n)})}</ha-button
  >`}var gt=new WeakMap;function _t(e){let t=e.entities,n=gt.get(t);if(n)return n;let r=new Map,i=new Map;for(let t of Object.values(e.entities??{}))if(t.platform===`ausnz_disaster_watch`&&t.device_id){if(t.translation_key){let e=r.get(t.device_id);e||r.set(t.device_id,e=new Map),e.set(t.translation_key,t.entity_id)}if(t.entity_id.startsWith(`camera.`)){let e=i.get(t.device_id)??[];e.push(t.entity_id),i.set(t.device_id,e)}}let a=new Set([...r.keys(),...i.keys()]),o=Object.keys(e.devices??{}).filter(e=>a.has(e));for(let e of a)o.includes(e)||o.push(e);let s={devices:o,byKey:r,cameras:i};return gt.set(t,s),s}function W(e){return _t(e).devices}function vt(e,t){return t||W(e)[0]}function yt(e,t){return!!t&&W(e).includes(t)}function bt(t,n){if(!n)return;let r=t.devices?.[n];if(!r)return;let i=r.identifiers?.find(([t])=>t===e);return i?i[1]:r.config_entries?.[0]}function xt(e,t){if(!t)return;let n=e.devices?.[t];return n?.name_by_user||n?.name||void 0}function St(e,t,n){if(t)return _t(e).byKey.get(t)?.get(n)}function G(e,t,n){let r=St(e,t,n);return r?e.states[r]:void 0}function Ct(e,t){return t?[..._t(e).cameras.get(t)??[]].sort((t,n)=>{let r=String(e.states[t]?.attributes.friendly_name??t),i=String(e.states[n]?.attributes.friendly_name??n);return r.localeCompare(i)}):[]}var wt=new WeakMap;function Tt(e,t){if(!t)return[];let n=wt.get(e.states);n||wt.set(e.states,n=new Map);let r=n.get(t);if(r)return r;let i=Object.values(e.states).filter(e=>e.entity_id.startsWith(`geo_location.`)&&e.attributes.integration===`ausnz_disaster_watch`&&e.attributes.entry_id===t).sort((e,t)=>(Dt(e)??1/0)-(Dt(t)??1/0));return n.set(t,i),i}function Et(e){let t=e.attributes.title??e.attributes.friendly_name;return typeof t==`string`&&t?t:e.entity_id}function Dt(e){let t=Number.parseFloat(e.state);if(Number.isFinite(t))return t;let n=e.attributes.distance_km;return typeof n==`number`&&Number.isFinite(n)?n:void 0}var Ot=[`ha-card`,`ha-icon`,`ha-icon-button`,`ha-button`,`ha-alert`,`ha-assist-chip`,`ha-filter-chip`,`ha-chip-set`,`ha-list-base`,`ha-list-item-base`,`ha-list-item-button`,`ha-tooltip`],kt;function At(e=5e3){return kt??=(async()=>{try{await window.loadCardHelpers?.()}catch{}await Promise.race([Promise.all(Ot.map(e=>customElements.whenDefined(e))),new Promise(t=>setTimeout(t,e))])})(),kt}var jt=y`
  :host {
    display: block;
    height: 100%;
    font-family: var(--ha-font-family-body);
    color: var(--primary-text-color);
    -webkit-font-smoothing: var(--ha-font-smoothing);
  }
  :host([embedded]) {
    height: auto;
  }
  ha-card,
  section.embedded {
    container-type: inline-size;
  }
  ha-card {
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  section.embedded {
    display: flex;
    flex-direction: column;
  }
  .header {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2);
    min-height: var(--ha-space-12);
    padding: var(--ha-space-2) var(--ha-space-2) 0 var(--ha-space-4);
  }
  .header ha-icon {
    color: var(--secondary-text-color);
    flex: none;
  }
  .header .heading {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .header .subtitle {
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    line-height: var(--ha-line-height-condensed);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .header .title {
    min-width: 0;
    margin: 0;
    font-family: var(--ha-font-family-heading);
    font-size: var(--ha-font-size-l);
    font-weight: var(--ha-font-weight-medium);
    line-height: var(--ha-line-height-condensed);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .header .count {
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    font-weight: var(--ha-font-weight-normal);
  }
  .header .actions {
    display: flex;
    align-items: center;
    flex: none;
    color: var(--secondary-text-color);
  }
  .content {
    display: flex;
    flex-direction: column;
    gap: var(--ha-space-3);
    padding: var(--ha-space-2) var(--ha-space-4) var(--ha-space-4);
    min-height: 0;
  }
  .secondary {
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    line-height: var(--ha-line-height-normal);
  }
  .list {
    display: flex;
    flex-direction: column;
    margin: 0 calc(-1 * var(--ha-space-4));
  }
  .list-title {
    margin: var(--ha-space-2) 0 0;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s);
    font-weight: var(--ha-font-weight-medium);
    letter-spacing: 0.02em;
  }
  .row {
    display: flex;
    align-items: center;
    min-width: 0;
  }
  /* HA's row tokens (ha-row-item, 2026.11): entities-card spacing. */
  .row .item {
    flex: 1;
    min-width: 0;
    --ha-row-item-padding-inline: var(--ha-space-4);
    --ha-row-item-padding-block: var(--ha-space-2);
    --ha-row-item-gap: var(--ha-space-3);
    --ha-list-item-focus-radius: var(--ha-border-radius-lg);
  }
  /* HA's list item draws its own focus ring. */
  .row .item:focus-visible {
    outline: none;
  }
  .row .link {
    flex: none;
    margin-inline-end: var(--ha-space-2);
    color: var(--secondary-text-color);
  }
  .row .headline,
  .row .supporting {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .row .row-badge {
    display: flex;
    flex-wrap: wrap;
    gap: var(--ha-space-1);
    margin: var(--ha-space-1) 0;
  }
  .row .trailing {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: var(--ha-space-1);
    white-space: nowrap;
  }
  .bubble {
    --tone: var(--grey-color);
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--ha-space-9);
    height: var(--ha-space-9);
    border-radius: var(--ha-border-radius-pill);
    background-color: color-mix(in srgb, var(--tone) 20%, transparent);
    color: var(--tone);
  }
  .bubble.large {
    width: var(--ha-space-12);
    height: var(--ha-space-12);
  }
  .badge {
    --tone: var(--grey-color);
    display: inline-flex;
    align-items: center;
    gap: var(--ha-space-1);
    max-width: 100%;
    padding: 0 var(--ha-space-2);
    min-height: var(--ha-space-6);
    border-radius: var(--ha-border-radius-pill);
    background-color: color-mix(in srgb, var(--tone) 18%, transparent);
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-s);
    font-weight: var(--ha-font-weight-medium);
    line-height: var(--ha-line-height-condensed);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .badge ha-icon {
    color: var(--tone);
    --mdc-icon-size: var(--ha-space-4);
    flex: none;
  }
  .empty {
    display: flex;
    align-items: center;
    gap: var(--ha-space-3);
    padding: var(--ha-space-2) 0;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-m);
  }
  .empty ha-icon {
    flex: none;
  }
  ha-chip-set {
    display: flex;
    flex-wrap: wrap;
    gap: var(--ha-space-2);
  }
  ha-alert {
    display: block;
  }
  .more {
    align-self: flex-start;
  }
  hr.divider {
    width: 100%;
    margin: 0;
    border: none;
    border-top: var(--ha-border-width-sm) solid var(--divider-color);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  :where(button.plain) {
    all: unset;
    box-sizing: border-box;
    cursor: pointer;
    border-radius: var(--ha-border-radius-lg);
  }
  :focus-visible {
    outline: var(--ha-border-width-md) solid var(--ha-color-focus, var(--primary-color));
    outline-offset: var(--ha-border-width-md);
  }
  /* Narrow sections-view cells (3 of 12 columns). */
  @container (max-width: 240px) {
    .header > ha-icon {
      display: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      animation: none !important;
      transition: none !important;
    }
  }
`;function Mt(e,t,n){e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0}))}function Nt(e,t){t&&Mt(e,`hass-more-info`,{entityId:t})}var Pt={emergency:{level:`emergency`,tone:`red`,icon:`mdi:alert-octagon`,rank:4},watch_and_act:{level:`watch_and_act`,tone:`orange`,icon:`mdi:alert`,rank:3},advice:{level:`advice`,tone:`amber`,icon:`mdi:information`,rank:2},information:{level:`information`,tone:`blue`,icon:`mdi:information-outline`,rank:1},unknown:{level:`unknown`,tone:`grey`,icon:`mdi:help-circle-outline`,rank:0}};function Ft(e){if(typeof e!=`string`)return`unknown`;let t=e.trim().toLowerCase().replace(/_/g,` `);return t.includes(`emergency`)?`emergency`:t.includes(`watch and act`)||t.includes(`watch & act`)?`watch_and_act`:t.includes(`advice`)?`advice`:t.includes(`info`)||t.includes(`routine`)||t.includes(`notification`)?`information`:`unknown`}function K(e){return Pt[Ft(e)]}function It(e,t){return e===`unknown`&&t!==void 0&&t>0?`unknown`:e===void 0||e===`unavailable`||e===`unknown`?`unavailable`:e.trim().toLowerCase().replace(/_/g,` `)===`all clear`?t===void 0||t>0?`unknown`:`all_clear`:Ft(e)}function Lt(e){return e===`all_clear`?{level:`unknown`,tone:`green`,icon:`mdi:shield-check`,rank:0}:e===`unavailable`?{level:`unknown`,tone:`grey`,icon:`mdi:cloud-off-outline`,rank:-1}:Pt[e]}var Rt=[`council`,`radius`];function zt(e){if(!e||typeof e!=`object`)return;let t=e,n=I(t.name);return n?{name:n,code:I(t.code)}:void 0}function Bt(e,t){return e===`council`?t?{council:t,fallback:!1,keep:e=>e!==!1}:{fallback:!0,keep:()=>!0}:{fallback:!1,keep:()=>!0}}function Vt(e){let t=e[0];if(!t)return{level:`all_clear`,count:0};let n=t,r;for(let t of e)K(t.level).rank>K(n.level).rank&&(n=t),t.distanceKm!==void 0&&(r?.distanceKm===void 0||t.distanceKm<r.distanceKm)&&(r=t);return{level:K(n.level).rank>0?String(n.level):`unknown`,count:e.length,nearestKm:r?.distanceKm,nearestTitle:r?.title}}var q=class extends j{static properties={hass:{attribute:!1},embedded:{type:Boolean,reflect:!0},_config:{state:!0}};static styles=[jt];constructor(){super(),this.embedded=!1}entityKeys(){return[]}static defaultArea;usesIncidents=!1;extraEntityIds(e){return[]}static validateConfig(e){if(!e||typeof e!=`object`)throw Error(`Invalid configuration`);if(e.device!==void 0&&typeof e.device!=`string`)throw Error(`'device' must be a device ID`);if(e.title!==void 0&&typeof e.title!=`string`)throw Error(`'title' must be text`);Kt(e,`area`,Rt)}setConfig(e){this.constructor.validateConfig(e),this._config={...e}}get config(){return this._config}get deviceId(){return this.hass?vt(this.hass,this._config?.device):void 0}get entryId(){return this.hass?bt(this.hass,this.deviceId):void 0}entityId(e){return this.hass?St(this.hass,this.deviceId,e):void 0}cardTitle(){return this._config?.title||f(this.hass,this.titleKey)}areaFilter(e){let t=this.constructor.defaultArea;if(!t)return Bt(`radius`,void 0);let r=G(e,this.deviceId,n.highestWarningLevel);return Bt(this._config?.area??t,zt(r?.attributes.council_area))}areaHint(e,t){return t.fallback?E`<span class="secondary">${f(e,`area.fallback`)}</span>`:O}moreInfo(e){Nt(this,e)}trackedEntityIds(e){let t=vt(e,this._config?.device),r=[],i=[...this.entityKeys()];this.constructor.defaultArea&&i.push(n.highestWarningLevel);for(let n of i){let i=St(e,t,n);i&&r.push(i)}if(this.usesIncidents)for(let n of Tt(e,bt(e,t)))r.push(n.entity_id);return r.push(...this.extraEntityIds(e)),r}shouldUpdate(e){if(!e.has(`hass`)||e.size>1)return!0;let t=e.get(`hass`),n=this.hass;if(!t||!n||t.entities!==n.entities||t.devices!==n.devices||t.locale!==n.locale||t.themes?.darkMode!==n.themes?.darkMode)return!0;let r=new Set([...this.trackedEntityIds(t),...this.trackedEntityIds(n)]);for(let e of r)if(t.states[e]!==n.states[e])return!0;return!1}connectedCallback(){super.connectedCallback(),At()}getCardSize(){return 3}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}renderSetupState(e){if(W(e).length===0)return E`<div class="content">${B(`info`,f(e,`state.not_set_up`))}</div>`;if(this._config?.device&&!yt(e,this._config.device))return E`<div class="content">${B(`warning`,f(e,`state.device_missing`))}</div>`}render(){if(!this._config||!this.hass)return O;let e=this.renderSetupState(this.hass)??this.renderBody(this.hass,this._config);return this.embedded?E`<section class="embedded" aria-label=${this.cardTitle()}>${e}</section>`:E`<ha-card>${e}</ha-card>`}};function J(e){let t=e?W(e)[0]:void 0;return t?{device:t}:{}}function Y(e){return{name:`area`,default:e,selector:{select:{mode:`dropdown`,options:Rt.map(e=>({value:e,label:f(void 0,`editor.area.${e}`)}))}}}}function X(){return[{name:`device`,selector:{device:{filter:{integration:e}}}},{name:`title`,selector:{text:{}}}]}var Ht={device:`editor.device`,title:`editor.title`,max_items:`editor.max_items`,show_planned_burns:`editor.show_planned_burns`,show_nearby_councils:`editor.show_nearby_councils`,area:`editor.area`,categories:`editor.categories`,refresh_interval:`editor.refresh_interval`,zoom:`editor.zoom`,radar:`editor.radar`,radar_opacity:`editor.radar_opacity`,satellite_layer:`editor.satellite_layer`,show_cyclone_tracks:`editor.show_cyclone_tracks`,cards:`editor.cards`},Ut={device:`editor.device_helper`,title:`editor.title_helper`,max_items:`editor.max_items_helper`,show_planned_burns:`editor.show_planned_burns_helper`,show_nearby_councils:`editor.show_nearby_councils_helper`,area:`editor.area_helper`,categories:`editor.categories_helper`,refresh_interval:`editor.refresh_interval_helper`,zoom:`editor.zoom_helper`,radar:`editor.radar_helper`,satellite_layer:`editor.satellite_layer_helper`,show_cyclone_tracks:`editor.show_cyclone_tracks_helper`,cards:`editor.cards_helper`},Z=e=>{let t=Ht[e.name];return t?f(void 0,t):void 0},Q=e=>{let t=Ut[e.name];return t?f(void 0,t):void 0};function $(e,t,n=1,r=1e3){let i=e[t];if(i!=null&&(typeof i!=`number`||!Number.isInteger(i)||i<n||i>r))throw Error(`'${t}' must be a whole number from ${n} to ${r}`)}function Wt(e,t,n,r){let i=e[t];if(i!=null&&(typeof i!=`number`||!Number.isFinite(i)||i<n||i>r))throw Error(`'${t}' must be a number from ${n} to ${r}`)}function Gt(e,t){let n=e[t];if(n!==void 0&&typeof n!=`boolean`)throw Error(`'${t}' must be true or false`)}function Kt(e,t,n){let r=e[t];if(r!=null&&(typeof r!=`string`||!n.includes(r)))throw Error(`'${t}' must be one of: ${n.join(`, `)}`)}function qt(e,t,n){let r=e[t];if(r!=null&&(!Array.isArray(r)||r.some(e=>typeof e!=`string`||!n.includes(e))))throw Error(`'${t}' must be a list of: ${n.join(`, `)}`)}var Jt={status:`card.status.name`,incidents:`card.incidents.name`,warnings:`card.warnings.name`,fire_danger:`card.fire_danger.name`,outages:`card.outages.name`,roads:`card.roads.name`,conditions:`card.conditions.name`,relief:`card.relief.name`,cameras:`card.cameras.name`,map:`card.map.name`},Yt=class e extends j{static properties={_config:{state:!0}};static styles=[jt,y`
      .title {
        margin: 0;
        padding: var(--ha-space-4) var(--ha-space-4) 0;
        font-family: var(--ha-font-family-heading);
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-medium);
        line-height: var(--ha-line-height-condensed);
      }
    `];_children=new Map;_hass;set hass(e){let t=e=>!!e&&W(e).length>0;if((t(e)!==t(this._hass)||!this._hass)&&this.requestUpdate(),this._hass=e,e)for(let t of this._children.values())t.hass=e}get hass(){return this._hass}static validateConfig(e){q.validateConfig(e),qt(e,`cards`,o),Gt(e,`show_nearby_councils`)}static getConfigForm(){return{schema:[...X(),{name:`cards`,selector:{select:{multiple:!0,reorder:!0,mode:`list`,options:o.map(e=>({value:e,label:f(void 0,Jt[e])}))}}},{name:`show_nearby_councils`,selector:{boolean:{}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}setConfig(t){e.validateConfig(t),this._config={...t}}sections(){return this._config?.cards?.length?this._config.cards:a}connectedCallback(){super.connectedCallback(),At()}getCardSize(){return this.sections().length*3}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}willUpdate(e){if(this._config){if(e.has(`_config`)){let e=new Set(this.sections());for(let t of[...this._children.keys()])e.has(t)||this._children.delete(t);for(let t of e){let e=this._children.get(t);e||(e=document.createElement(r[t]),e.embedded=!0,this._children.set(t,e));let n=t===`relief`?{show_nearby_councils:this._config.show_nearby_councils}:{};e.setConfig({type:`custom:${r[t]}`,device:this._config.device,...n})}}if(this._hass)for(let e of this._children.values())e.hass=this._hass}}render(){if(!this._config)return O;let e=this.sections().map(e=>this._children.get(e)).filter(e=>!!e);return this._hass&&W(this._hass).length===0?E`<ha-card><div class="content">${B(`info`,f(this._hass,`state.not_set_up`))}</div></ha-card>`:E`<ha-card>
      ${this._config.title?E`<h2 class="title">${this._config.title}</h2>`:O}
      ${e.map((e,t)=>E`${t?E`<hr class="divider" />`:O}${e}`)}
    </ha-card>`}},Xt=e=>`/api/camera_proxy/${e}`,Zt=10,Qt=class extends q{static properties={...q.properties,_tick:{state:!0},_failed:{state:!0},_signed:{state:!0}};static styles=[...q.styles,y`
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
    `];_signing=new Set;titleKey=`cameras.title`;static defaultArea=`council`;_timer;_observer;_visible=!1;_onVisibility=()=>this.updateTimer();constructor(){super(),this._tick=0,this._failed=new Set,this._signed={}}extraEntityIds(e){return Ct(e,vt(e,this.config?.device))}static validateConfig(e){super.validateConfig(e),$(e,`refresh_interval`,Zt,3600)}static getConfigForm(){return{schema:[...X(),Y(this.defaultArea),{name:`refresh_interval`,selector:{number:{min:Zt,max:3600,step:5,mode:`box`,unit_of_measurement:`s`}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getCardSize(){return 4}connectedCallback(){super.connectedCallback(),document.addEventListener(`visibilitychange`,this._onVisibility),`IntersectionObserver`in window?(this._observer=new IntersectionObserver(e=>{this._visible=e.some(e=>e.isIntersecting),this.updateTimer()}),this._observer.observe(this)):(this._visible=!0,this.updateTimer())}disconnectedCallback(){super.disconnectedCallback(),document.removeEventListener(`visibilitychange`,this._onVisibility),this._observer?.disconnect(),this._observer=void 0,this._visible=!1,this.updateTimer()}updated(e){super.updated(e),this.signMissing(),e.has(`_config`)&&this._timer&&(clearInterval(this._timer),this._timer=void 0,this.updateTimer())}updateTimer(){let e=this._visible&&document.visibilityState===`visible`&&this.isConnected;if(e&&!this._timer){let e=this._config?.refresh_interval??60;this._timer=setInterval(()=>{this._failed=new Set,this._tick+=1},e*1e3)}else!e&&this._timer&&(clearInterval(this._timer),this._timer=void 0)}signMissing(){let e=this.hass;if(e)for(let t of this.cameraIds(e)){let n=e.states[t];if(!n||M(n)||I(n.attributes.entity_picture))continue;let r=`${t}@${this._tick}`;this._signed[r]||this._signing.has(r)||(this._signing.add(r),e.connection.sendMessagePromise({type:`auth/sign_path`,path:Xt(t),expires:300}).then(e=>{e?.path&&(this._signed={...this.prune(),[r]:e.path})}).catch(()=>void 0).finally(()=>this._signing.delete(r)))}}cameraIds(e){let t=this.areaFilter(e);return Ct(e,this.deviceId).filter(n=>t.keep(e.states[n]?.attributes.in_council_area))}prune(){return Object.fromEntries(Object.entries(this._signed).filter(([e])=>e.endsWith(`@${this._tick}`)))}imageUrl(e){return this._tick?`${e}${e.includes(`?`)?`&`:`?`}t=${this._tick}`:e}renderBody(e,t){let n=this.cameraIds(e),r=this.areaFilter(e);return E`${V({title:this.cardTitle(),icon:`mdi:cctv`,count:n.length?N(e,n.length):void 0,subtitle:r.council?.name})}
      <div class="content">
        ${this.areaHint(e,r)}
        ${n.length?E`<div class="grid" role="list">
                ${n.map(t=>{let n=e.states[t],r=it(e,t,!0),i=M(n)?void 0:I(n?.attributes.entity_picture),a=i?this.imageUrl(i):this._signed[`${t}@${this._tick}`],o=a&&!this._failed.has(a);return E`<div role="listitem">
                    <button class="plain camera" aria-label=${`${r}. ${f(e,`action.details`)}`} @click=${()=>this.moreInfo(t)}>
                      <span class="frame">
                        ${o?E`<img
                                src=${a}
                                alt=${r}
                                loading="lazy"
                                @error=${()=>this._failed=new Set([...this._failed,a])}
                              />`:E`<span class="placeholder">
                                <ha-icon icon="mdi:image-off-outline" aria-hidden="true"></ha-icon>
                                <span>${f(e,`cameras.no_image`)}</span>
                              </span>`}
                      </span>
                      <span class="name">${r}</span>
                    </button>
                  </div>`})}
              </div>`:z(`mdi:cctv-off`,f(e,`cameras.empty`))}
      </div>`}},$t=[`moderate`,`high`,`extreme`,`catastrophic`],en={moderate:`green`,high:`yellow`,extreme:`orange`,catastrophic:`red`,no_rating:`grey`},tn={moderate:`mdi:fire`,high:`mdi:fire`,extreme:`mdi:fire-alert`,catastrophic:`mdi:fire-alert`,no_rating:`mdi:fire-off`};function nn(e){if(typeof e!=`string`)return`no_rating`;let t=e.trim().toLowerCase();return t.includes(`catastrophic`)?`catastrophic`:t.includes(`extreme`)?`extreme`:t.includes(`high`)?`high`:t.includes(`moderate`)?`moderate`:`no_rating`}function rn(e){return en[e]}var an={good:`green`,fair:`yellow`,poor:`orange`,very_poor:`red`,extremely_poor:`purple`,unknown:`grey`};function on(e){if(typeof e!=`string`)return`unknown`;let t=e.trim().toLowerCase();return t.includes(`extremely`)||t.includes(`hazardous`)?`extremely_poor`:t.includes(`very poor`)||t.includes(`very_poor`)?`very_poor`:t.includes(`poor`)?`poor`:t.includes(`fair`)||t.includes(`moderate`)?`fair`:t.includes(`good`)||t.includes(`very good`)?`good`:`unknown`}function sn(e){return an[e]}function cn(e){if(typeof e!=`string`)return`grey`;let t=e.toLowerCase();return t.includes(`closed`)||t.includes(`closure`)?`red`:t.includes(`flood`)?`blue`:t.includes(`hazard`)||t.includes(`caution`)||t.includes(`restrict`)||t.includes(`lane`)?`amber`:t.includes(`open`)?`green`:`grey`}function ln(e){let t=cn(e);return t===`red`?`mdi:road-variant`:t===`blue`?`mdi:waves`:t===`amber`?`mdi:traffic-cone`:`mdi:road`}var un=[`N`,`NNE`,`NE`,`ENE`,`E`,`ESE`,`SE`,`SSE`,`S`,`SSW`,`SW`,`WSW`,`W`,`WNW`,`NW`,`NNW`];function dn(e){return un[Math.round((e%360+360)%360/22.5)%16]}var fn=[{attr:`pm2_5`,label:`PM2.5`},{attr:`pm10`,label:`PM10`},{attr:`no2`,label:`NO₂`},{attr:`o3`,label:`O₃`}],pn=class extends q{static styles=[...q.styles,y`
      .group {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
      }
      .group-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--ha-space-2);
      }
      .group-title {
        margin: 0;
        font-size: var(--ha-font-size-m);
        font-weight: var(--ha-font-weight-medium);
      }
      .temperature {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: var(--ha-space-2);
      }
      .temperature .value {
        font-size: var(--ha-font-size-3xl);
        font-weight: var(--ha-font-weight-normal);
        line-height: var(--ha-line-height-condensed);
      }
      .metrics {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(calc(var(--ha-space-20) + var(--ha-space-8)), 1fr));
        gap: var(--ha-space-2) var(--ha-space-4);
        margin: 0;
      }
      .metric {
        display: flex;
        flex-direction: column;
        min-width: 0;
      }
      .metric dt {
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-s);
      }
      .metric dd {
        margin: 0;
        display: flex;
        align-items: center;
        gap: var(--ha-space-1);
        font-size: var(--ha-font-size-m);
        font-weight: var(--ha-font-weight-medium);
      }
      .metric dd ha-icon {
        --mdc-icon-size: var(--ha-space-4);
        color: var(--secondary-text-color);
      }
    `];titleKey=`conditions.title`;entityKeys(){return[n.primaryWeatherObservation,n.airQualityRating]}static getConfigForm(){return{schema:X(),computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getCardSize(){return 4}metric(e,t){return t===void 0||t===``?O:E`<div class="metric"><dt>${e}</dt><dd>${t}</dd></div>`}renderWeather(e,t){if(!t||M(t))return z(`mdi:weather-cloudy-alert`,f(e,`conditions.no_weather`));let n=t.attributes,r=(r,i)=>{let a=F(n[r]);return a===void 0?void 0:`${ot(e,t,r,a)} ${i}`},i=F(n.wind_direction_deg),a=r(`wind_speed_avg_kph`,`km/h`),o=F(L(n.stations)[0]?.rain_since_9am),s=I(n.station_name),c=a===void 0?void 0:E`${i===void 0?O:E`<ha-icon
                    icon="mdi:navigation"
                    style=${et({transform:`rotate(${i+180}deg)`})}
                    aria-hidden="true"
                  ></ha-icon>`}<span>${a}${i===void 0?``:` ${dn(i)}`}</span>${i===void 0?O:E`<span class="sr-only">${f(e,`conditions.wind_from`,{direction:dn(i)})}</span>`}`;return E`<button
        class="plain temperature"
        aria-label=${`${f(e,`conditions.temperature`)} ${at(e,t)}. ${f(e,`action.details`)}`}
        @click=${()=>this.moreInfo(t.entity_id)}
      >
        <span class="value">${at(e,t)}</span>
        ${s?E`<span class="secondary">${f(e,`conditions.station`,{name:s})}</span>`:O}
      </button>
      <dl class="metrics">
        ${this.metric(f(e,`conditions.feels_like`),r(`apparent_temperature`,`°C`))}
        ${this.metric(f(e,`conditions.humidity`),r(`relative_humidity`,`%`))}
        ${this.metric(f(e,`conditions.wind`),c)}
        ${this.metric(f(e,`conditions.gust`),r(`wind_speed_max_kph`,`km/h`))}
        ${this.metric(f(e,`conditions.pressure`),r(`pressure_hpa`,`hPa`))}
        ${this.metric(f(e,`conditions.rain`),o===void 0?void 0:`${ot(e,t,`rain_since_9am`,o)} mm`)}
      </dl>`}renderAirQuality(e,t){if(!t||M(t))return z(`mdi:air-filter`,f(e,`conditions.no_air_quality`));let n=I(t.attributes.station_name);return E`<dl class="metrics">
        ${fn.map(n=>this.metric(n.label,I(t.attributes[n.attr])??(F(t.attributes[n.attr])===void 0?void 0:ot(e,t,n.attr))))}
      </dl>
      ${n?E`<span class="secondary">${f(e,`conditions.station`,{name:n})}</span>`:O}`}renderBody(e,t){let r=G(e,this.deviceId,n.primaryWeatherObservation),i=G(e,this.deviceId,n.airQualityRating),a=on(M(i)?void 0:i?.state),o=M(i)?void 0:a===`unknown`?I(i?.state):f(e,`conditions.aq.${a}`);return E`${V({title:this.cardTitle(),icon:`mdi:weather-partly-cloudy`})}
      <div class="content">
        <section class="group" aria-label=${f(e,`conditions.weather`)}>${this.renderWeather(e,r)}</section>
        <hr class="divider" />
        <section class="group" aria-label=${f(e,`conditions.air_quality`)}>
          <div class="group-head">
            <h3 class="group-title">${f(e,`conditions.air_quality`)}</h3>
            ${o?E`<button class="plain" aria-label=${`${f(e,`conditions.air_quality`)}: ${o}. ${f(e,`action.details`)}`} @click=${()=>this.moreInfo(i?.entity_id)}>
                    ${R(o,sn(a),`mdi:air-filter`)}
                  </button>`:O}
          </div>
          ${this.renderAirQuality(e,i)}
        </section>
      </div>`}},mn=class extends q{static styles=[...q.styles,y`
      .rating {
        display: flex;
        align-items: center;
        gap: var(--ha-space-3);
      }
      .rating-text {
        display: flex;
        flex-direction: column;
        min-width: 0;
      }
      @container (max-width: 260px) {
        .rating {
          flex-direction: column;
          align-items: flex-start;
        }
      }
      .rating-label {
        overflow-wrap: anywhere;
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-bold);
        line-height: var(--ha-line-height-condensed);
      }
      .content {
        container-type: inline-size;
      }
      .scale {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: var(--ha-space-1);
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .segment {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1);
        min-width: 0;
        font-size: var(--ha-font-size-xs);
        color: var(--secondary-text-color);
        text-align: center;
      }
      .segment .bar {
        height: var(--ha-space-2);
        border-radius: var(--ha-border-radius-pill);
        background-color: color-mix(in srgb, var(--tone) 30%, transparent);
      }
      .segment.active {
        color: var(--primary-text-color);
        font-weight: var(--ha-font-weight-bold);
      }
      .segment.active .bar {
        background-color: var(--tone);
        box-shadow: 0 0 0 var(--ha-border-width-md) var(--card-background-color, var(--ha-card-background)),
          0 0 0 calc(2 * var(--ha-border-width-md)) var(--tone);
      }
      .segment .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      /* Narrow cards name only the current level under the scale; all names stay readable to screen readers. */
      @container (max-width: 300px) {
        .segment:not(.active) .name {
          position: absolute;
          width: 1px;
          height: 1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
        }
        .segment.active .name {
          overflow: visible;
        }
      }
      .badges {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ha-space-2);
      }
    `];titleKey=`fire.title`;entityKeys(){return[n.fireDangerRating]}static getConfigForm(){return{schema:X(),computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getGridOptions(){return{columns:6,rows:`auto`,min_columns:6}}renderBody(e,t){let r=G(e,this.deviceId,n.fireDangerRating),i=V({title:this.cardTitle(),icon:`mdi:fire`,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(!r||r.state===`unavailable`)return E`${i}<div class="content">
          ${B(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let a=nn(M(r)?void 0:r.state),o=rn(a),s=e.formatEntityState&&!M(r)?e.formatEntityState(r):f(e,`fire.rating.${a}`),c=I(r.attributes.district_name),l=I(r.attributes.day),u=r.attributes.total_fire_ban===!0;return E`${i}
      <div class="content">
        <div class="rating">
          ${mt(tn[a],o,!0)}
          <div class="rating-text">
            <span class="rating-label">${s}</span>
            ${c||l?E`<span class="secondary"
                    >${[c?f(e,`fire.district`,{district:c}):void 0,l?f(e,`fire.forecast_for`,{day:l}):void 0].filter(Boolean).join(` · `)}</span
                  >`:O}
          </div>
        </div>
        <ol class="scale" aria-label=${f(e,`fire.scale`)}>
          ${$t.map(t=>{let n=t===a,r=f(e,`fire.rating.${t}`);return E`<li
              class="segment ${n?`active`:``}"
              style=${et({"--tone":ft(rn(t))})}
              aria-current=${n?`true`:O}
            >
              <span class="bar" aria-hidden="true"></span>
              <span class="name">${r}</span>
              ${n?E`<span class="sr-only">${f(e,`fire.current`)}</span>`:O}
            </li>`})}
        </ol>
        <div class="badges">
          ${u?R(f(e,`fire.total_fire_ban`),`red`,`mdi:fire-off`):R(f(e,`fire.no_total_fire_ban`),`grey`,`mdi:check`)}
        </div>
      </div>`}},hn=[`fire`,`flood_storm`,`geological`,`roads`,`other`],gn={Bushfire:{category:`fire`,icon:`mdi:fire`},"Grass Fire":{category:`fire`,icon:`mdi:grass`},"Structure Fire":{category:`fire`,icon:`mdi:fire-alert`},Flood:{category:`flood_storm`,icon:`mdi:water-alert`},"Severe Storm":{category:`flood_storm`,icon:`mdi:weather-lightning`},"Tropical Cyclone":{category:`flood_storm`,icon:`mdi:weather-hurricane`},Earthquake:{category:`geological`,icon:`mdi:pulse`},Volcano:{category:`geological`,icon:`mdi:volcano`},Tsunami:{category:`geological`,icon:`mdi:tsunami`},"Road Hazard / Crash":{category:`roads`,icon:`mdi:car-emergency`},"Hazmat Incident":{category:`other`,icon:`mdi:biohazard`},Other:{category:`other`,icon:`mdi:alert-decagram`}},_n={fire:`mdi:fire`,flood_storm:`mdi:weather-pouring`,geological:`mdi:earth`,roads:`mdi:car-emergency`,other:`mdi:alert-decagram`};function vn(e){return typeof e==`string`&&gn[e]?.category||`other`}function yn(e){return typeof e==`string`&&gn[e]?.icon||`mdi:alert-decagram`}var bn=10,xn={emergency:`status.level.emergency`,watch_and_act:`status.level.watch_and_act`,advice:`status.level.advice`,information:`status.level.information`,unknown:`status.level.unknown`},Sn=class extends q{static properties={...q.properties,_category:{state:!0},_showBurns:{state:!0},_expanded:{state:!0}};titleKey=`incidents.title`;static defaultArea=`radius`;usesIncidents=!0;constructor(){super(),this._category=`all`,this._showBurns=void 0,this._expanded=!1}static validateConfig(e){super.validateConfig(e);let t=e;$(t,`max_items`,1,100),Gt(t,`show_planned_burns`),qt(t,`categories`,hn)}static getConfigForm(){return{schema:[...X(),Y(this.defaultArea),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}},{name:`show_planned_burns`,selector:{boolean:{}}},{name:`categories`,selector:{select:{multiple:!0,mode:`list`,options:hn.map(e=>({value:e,label:f(void 0,`incidents.category.${e}`)}))}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getCardSize(){return 2+Math.min(this._config?.max_items??bn,6)}get showBurns(){return this._showBurns??this._config?.show_planned_burns??!1}categories(){let e=this._config?.categories;return e?.length?e:hn}renderIncident(e,t){let n=t.attributes,r=K(n.warning_level),i=Et(t),a=lt(e,n.updated_at),o=[I(n.location_name),P(e,Dt(t)),a?f(e,`incidents.updated`,{time:a}):void 0].filter(Boolean).join(` · `);return H({icon:I(n.icon)??yn(n.hazard_type),tone:r.tone,headline:i,supporting:E`${n.is_hazard_reduction?E`${f(e,`incidents.planned_burn`)} · `:O}${o}`,badge:R(f(e,xn[r.level]),r.tone,r.icon),onActivate:()=>this.moreInfo(t.entity_id),link:dt(n.web_url),linkLabel:`${f(e,`action.open_link`)}: ${i}`,actions:this.renderNearestCamera(e,t)})}renderNearestCamera(e,t){let n=t.attributes.nearest_camera,r=I(n?.entity_id);if(!r?.startsWith(`camera.`)||!e.states[r])return;let i=I(n?.name)??it(e,r),a=P(e,F(n?.distance_km));return E`<ha-icon-button class="link camera" .label=${f(e,`incidents.nearest_camera`,{name:a?`${i}, ${a}`:i})} @click=${()=>this.moreInfo(r)}>
      <ha-icon icon="mdi:cctv"></ha-icon>
    </ha-icon-button>`}renderBody(e,t){let n=this.categories(),r=this.areaFilter(e),i=Tt(e,this.entryId).filter(e=>n.includes(vn(e.attributes.hazard_type))&&r.keep(e.attributes.in_council_area)),a=i.some(e=>e.attributes.is_hazard_reduction===!0),o=this.showBurns?i:i.filter(e=>e.attributes.is_hazard_reduction!==!0),s=new Map;for(let e of o){let t=vn(e.attributes.hazard_type);s.set(t,(s.get(t)??0)+1)}let c=this._category!==`all`&&n.includes(this._category)?this._category:`all`,l=c===`all`?o:o.filter(e=>vn(e.attributes.hazard_type)===c),u=t.max_items??bn,d=this._expanded?l:l.slice(0,u),p=(t,n)=>E`<ha-filter-chip
      .selected=${c===t}
      .label=${`${f(e,`incidents.category.${t}`)} ${N(e,n)}`}
      @click=${e=>{e.preventDefault(),this._category=t,this._expanded=!1}}
    >
      ${t===`all`?O:E`<ha-icon slot="icon" .icon=${_n[t]}></ha-icon>`}
    </ha-filter-chip>`;return E`${V({title:this.cardTitle(),icon:`mdi:alert-decagram`,count:N(e,o.length),subtitle:r.council?.name})}
      <div class="content">
        ${this.areaHint(e,r)}
        ${i.length?E`<ha-chip-set aria-label=${f(e,`incidents.filters`)}>
                ${p(`all`,o.length)}
                ${n.length>1?n.map(e=>p(e,s.get(e)??0)):O}
                ${a?E`<ha-filter-chip
                        .selected=${this.showBurns}
                        .label=${f(e,`incidents.planned_burns`)}
                        @click=${e=>{e.preventDefault(),this._showBurns=!this.showBurns}}
                      >
                        <ha-icon slot="icon" icon="mdi:fire-circle"></ha-icon>
                      </ha-filter-chip>`:O}
              </ha-chip-set>`:O}
        ${d.length?U(d.map(t=>this.renderIncident(e,t)),this.cardTitle()):z(`mdi:shield-check-outline`,f(e,i.length?`incidents.empty_filtered`:`incidents.empty`))}
        ${l.length>u?ht(e,this._expanded,l.length,()=>this._expanded=!this._expanded):O}
      </div>`}},Cn=`<a href="https://www.gdacs.org/About/termofuse.aspx" target="_blank" rel="noopener noreferrer">GDACS</a> (EC JRC / UN OCHA)`,wn=18e5,Tn=500;function En(e){if(typeof e!=`string`)return!1;let t;try{t=new URL(e)}catch{return!1}return t.origin===`https://www.gdacs.org`&&t.username===``&&t.password===``&&t.pathname===`/gdacsapi/api/polygons/getgeometry`&&t.searchParams.get(`eventtype`)===`TC`&&/^\d+$/.test(t.searchParams.get(`eventid`)??``)&&/^\d+$/.test(t.searchParams.get(`episodeid`)??``)}function Dn(e){if(!Array.isArray(e))return[];let t=[],n=new Set;for(let r of e){if(!r||typeof r!=`object`)continue;let{geometry_url:e,title:i}=r;if(En(e)&&!n.has(e)&&(n.add(e),t.push({url:e,name:typeof i==`string`?i:``}),t.length>=5))break}return t}function On(e,t){if(typeof e==`string`){if(e===`Poly_Green`)return`buffer-green`;if(e===`Poly_Orange`)return`buffer-orange`;if(e===`Poly_Red`)return`buffer-red`;if(e===`Poly_Cones`)return`cone`;if(e.startsWith(`Line_`))return t===!0?`track-forecast`:`track`}}var kn={"buffer-green":[`Polygon`,`MultiPolygon`],"buffer-orange":[`Polygon`,`MultiPolygon`],"buffer-red":[`Polygon`,`MultiPolygon`],cone:[`Polygon`,`MultiPolygon`],track:[`LineString`,`MultiLineString`],"track-forecast":[`LineString`,`MultiLineString`]};function An(e){if(!Array.isArray(e))return e;if(typeof e[0]==`number`){let[t,...n]=e;return[t<-90?t+360:t,...n]}return e.map(An)}var jn=[`cone`,`buffer-green`,`buffer-orange`,`buffer-red`,`track`,`track-forecast`];function Mn(e,t=``){let n=e;if(n?.type!==`FeatureCollection`||!Array.isArray(n.features))throw Error(`GDACS: not GeoJSON`);let r=[],i=t;for(let e of n.features.slice(0,Tn)){let t=e?.properties??{},n=e?.geometry,a=On(t.Class,t.forecast);a&&typeof n?.type==`string`&&Array.isArray(n.coordinates)&&kn[a].includes(n.type)&&(!i&&typeof t.name==`string`&&(i=t.name),r.push({part:a,geometry:{type:n.type,coordinates:An(n.coordinates)}}))}return r.sort((e,t)=>jn.indexOf(e.part)-jn.indexOf(t.part)),{name:i,shapes:r}}var Nn=new Map,Pn=new Map;async function Fn(e,t=Date.now(),n=fetch){if(!En(e.url))throw Error(`GDACS: URL not allowed`);let r=Nn.get(e.url);if(r&&t-r.at<wn)return r.data;let i=Pn.get(e.url);return i||(i=(async()=>{try{let r=await n(e.url,{credentials:`omit`,referrerPolicy:`no-referrer`});if(!r.ok)throw Error(`GDACS: HTTP ${r.status}`);let i=Mn(await r.json(),e.name);return Nn.set(e.url,{at:t,data:i}),i}finally{Pn.delete(e.url)}})(),Pn.set(e.url,i)),i}var In=`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best`,Ln=[`none`,`himawari_visible`,`himawari_ir`,`viirs_truecolor`],Rn=`<a href="https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance" target="_blank" rel="noopener noreferrer">NASA GIBS</a>`,zn=`Imagery: ${Rn} / Himawari-9 (JMA)`,Bn=`Imagery: ${Rn} / VIIRS NOAA-21`,Vn={himawari_visible:{id:`himawari_visible`,layer:`Himawari_AHI_Band3_Red_Visible_1km`,maxNativeZoom:7,format:`png`,cadence:`10min`,opacity:.6,attribution:zn},himawari_ir:{id:`himawari_ir`,layer:`Himawari_AHI_Band13_Clean_Infrared`,maxNativeZoom:6,format:`png`,cadence:`10min`,opacity:.6,attribution:zn},viirs_truecolor:{id:`viirs_truecolor`,layer:`VIIRS_NOAA21_CorrectedReflectance_TrueColor`,maxNativeZoom:9,format:`jpg`,cadence:`daily`,opacity:.9,attribution:Bn}},Hn=108e5,Un=6e5,Wn=864e5,Gn=2e3;function Kn(e){return`GoogleMapsCompatible_Level${e.maxNativeZoom}`}function qn(e){return new Date(Math.floor(e/6e4)*6e4).toISOString().replace(/:\d{2}\.\d{3}Z$/,`:00Z`)}function Jn(e){return new Date(e).toISOString().slice(0,10)}function Yn(e,t,n){return`${In}/1.0.0/${e.layer}/default/${Kn(e)}/all/${qn(t)}--${qn(n)}.xml`}function Xn(e,t){return`${In}/${e.layer}/default/${t}/${Kn(e)}/{z}/{y}/{x}.${e.format}`}var Zn=/^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$/;function Qn(e){let t=Zn.exec(e.trim());if(!t||e.trim()===`P`||e.trim()===`PT`)return;let[,n,r,i]=t,a=(Number(n??0)*24*60+Number(r??0)*60+Number(i??0))*6e4;return a>0?a:void 0}function $n(e){let t=[...e.matchAll(/<Domain>([^<]*)<\/Domain>/g)].map(e=>e[1]),n=new Set;for(let e of t)for(let t of e.split(`,`)){let[e,r,i]=t.trim().split(`/`),a=Date.parse(e??``);if(Number.isNaN(a))continue;let o=r?Date.parse(r):a,s=i?Qn(i):void 0;if(!(Number.isNaN(o)||o<a)){if(!s)n.add(a);else for(let e=a;e<=o&&n.size<Gn;e+=s)n.add(e)}}return[...n].sort((e,t)=>e-t)}var er=new Map,tr=new Map;async function nr(e,t=Date.now(),n=fetch,r=7){let i=er.get(e.id);if(i&&t-i.at<Un)return i.times;let a=tr.get(e.id);return a||(a=(async()=>{try{let i=await n(Yn(e,t-Hn,t),{credentials:`omit`,referrerPolicy:`no-referrer`});if(!i.ok)throw Error(`GIBS: HTTP ${i.status}`);let a=$n(await i.text()).filter(e=>e<=t).slice(-r);if(!a.length)throw Error(`GIBS: no frames`);return er.set(e.id,{at:t,times:a}),a}finally{tr.delete(e.id)}})(),tr.set(e.id,a)),a}var rr=[0,1,2];function ir(e){return new Date(e).getUTCHours()>=9?0:1}function ar(e,t){return Jn(e-t*Wn)}var or={radar:`off`,satellite:`off`,cyclones:`off`,cycloneCount:0},sr=(function(){let e=typeof document<`u`&&document.createElement(`link`).relList;return e&&e.supports&&e.supports(`modulepreload`)?`modulepreload`:`preload`})(),cr=function(e,t){return new URL(e,t).href},lr={},ur=function(e){return e.pathname.endsWith(`.css`)},dr=function(e,t,n){if(t in e)return e[t];let r=n();if(!r){e[t]=void 0;return}let i=r.then(()=>{e[t]=void 0},n=>{throw e[t]=void 0,n});return e[t]=i,i},fr=function(e,t,n){let r=Promise.resolve();if(t&&t.length>0){let e,i=document.querySelector(`meta[property=csp-nonce]`),a=i?.nonce||i?.getAttribute(`nonce`);function o(e){return Promise.all(e.map(e=>Promise.resolve(e).then(e=>({status:`fulfilled`,value:e}),e=>({status:`rejected`,reason:e}))))}function s(e){return import.meta.resolve?new URL(import.meta.resolve(e)):new URL(e,import.meta.url)}r=o(t.map(t=>{t=cr(t,n);let r=s(t),i=ur(r);return dr(lr,r.href,()=>{if(e===void 0){e={all:new Set,styles:new Set};let t=document.getElementsByTagName(`link`);for(let n=t.length-1;n>=0;n--){let r=t[n];e.all.add(r.href),r.rel===`stylesheet`&&e.styles.add(r.href)}}if((i?e.styles:e.all).has(r.href))return;let t=document.createElement(`link`);if(t.rel=i?`stylesheet`:sr,i||(t.as=`script`),t.crossOrigin=``,t.href=r.href,a&&t.setAttribute(`nonce`,a),document.head.appendChild(t),i)return new Promise((e,n)=>{t.addEventListener(`load`,e),t.addEventListener(`error`,()=>n(Error(`Unable to preload CSS for ${r}`)))})})}).filter(e=>e!==void 0))}function i(e){let t=new Event(`vite:preloadError`,{cancelable:!0});if(t.payload=e,window.dispatchEvent(t),!t.defaultPrevented)throw e}return r.then(t=>{for(let e of t||[])e.status===`rejected`&&i(e.reason);return e().catch(i)})},pr=.7,mr=[`_config`,`_satelliteHidden`,`_cyclonesHidden`,`_viirsDay`],hr,gr=()=>hr??=fr(()=>import(`./ausnz-disaster-leaflet-map-gaXO5OPJ.js`),[],import.meta.url),_r=class extends q{static properties={...q.properties,_status:{state:!0},_loadError:{state:!0},_satelliteHidden:{state:!0},_cyclonesHidden:{state:!0},_viirsDay:{state:!0}};static styles=[...q.styles,y`
      ha-card,
      section.embedded {
        min-height: calc(var(--ha-space-20) * 3.5);
      }
      .map-wrap {
        position: relative;
        flex: 1;
        min-height: calc(var(--ha-space-20) * 2.5);
        margin: var(--ha-space-2) 0 0;
      }
      :host([embedded]) .map-wrap {
        height: calc(var(--ha-space-20) * 4);
        flex: none;
      }
      .map {
        position: absolute;
        inset: 0;
        background-color: var(--ha-color-fill-neutral-quiet-resting);
        font-family: var(--ha-font-family-body);
        z-index: 0;
      }
      .map.dark .basemap {
        filter: invert(0.9) hue-rotate(170deg) brightness(1.5) contrast(1.2) saturate(0.3);
      }
      .map .leaflet-control-attribution {
        background-color: color-mix(in srgb, var(--card-background-color, var(--ha-card-background)) 80%, transparent);
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-xs);
      }
      .map .leaflet-control-attribution a {
        color: var(--primary-color);
      }
      .map .leaflet-bar {
        border: var(--ha-border-width-sm) solid var(--divider-color);
        box-shadow: none;
        border-radius: var(--ha-border-radius-md);
        overflow: hidden;
      }
      .map .leaflet-bar a {
        background-color: var(--card-background-color, var(--ha-card-background));
        color: var(--primary-text-color);
        border-bottom-color: var(--divider-color);
      }
      .map .leaflet-tooltip {
        background-color: var(--card-background-color, var(--ha-card-background));
        color: var(--primary-text-color);
        border: var(--ha-border-width-sm) solid var(--divider-color);
        border-radius: var(--ha-border-radius-md);
        box-shadow: none;
        font-family: var(--ha-font-family-body);
        font-size: var(--ha-font-size-s);
      }
      .map .leaflet-tooltip::before {
        display: none;
      }
      .map .radar-frame {
        transition: opacity var(--ha-animation-duration-slow) ease-in-out;
      }
      .map .incident {
        fill-opacity: 0.6;
        stroke-width: 2;
        cursor: pointer;
      }
      .map .incident:focus-visible {
        outline: none;
        stroke-width: 4;
        stroke: var(--primary-text-color);
      }
      .map .tone-red {
        fill: var(--red-color);
        stroke: var(--red-color);
      }
      .map .tone-orange {
        fill: var(--orange-color);
        stroke: var(--orange-color);
      }
      .map .tone-amber {
        fill: var(--amber-color);
        stroke: var(--amber-color);
      }
      .map .tone-blue {
        fill: var(--blue-color);
        stroke: var(--blue-color);
      }
      .map .tone-grey {
        fill: var(--grey-color);
        stroke: var(--grey-color);
      }
      .map .home-zone {
        fill: var(--primary-color);
        fill-opacity: 0.08;
        stroke: var(--primary-color);
        stroke-opacity: 0.6;
        stroke-dasharray: 4 4;
      }
      .map .home-dot {
        fill: var(--primary-color);
        fill-opacity: 1;
        stroke: var(--card-background-color, var(--ha-card-background));
        stroke-width: 2;
      }
      .radar-bar {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2);
        min-height: var(--ha-space-12);
        padding: 0 var(--ha-space-4) 0 var(--ha-space-1);
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-s);
      }
      .radar-bar .time {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .frames {
        display: flex;
        gap: var(--ha-space-1);
      }
      .frames span {
        width: var(--ha-space-2);
        height: var(--ha-space-2);
        border-radius: var(--ha-border-radius-pill);
        background-color: var(--ha-color-fill-neutral-normal-resting);
      }
      .frames span.current {
        background-color: var(--primary-color);
      }
      .notice {
        padding: 0 var(--ha-space-4) var(--ha-space-4);
      }
      .layers {
        padding: var(--ha-space-2) var(--ha-space-4) 0;
      }
      .legend {
        margin: 0;
        padding: var(--ha-space-1) var(--ha-space-4) var(--ha-space-2);
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-s);
      }
      .map .satellite-frame {
        transition: opacity var(--ha-animation-duration-slow) ease-in-out;
      }
      /* Loud fills at low opacity read on light, dark and satellite backgrounds alike. */
      .map .cyclone {
        stroke-opacity: 0.9;
      }
      .map .cyclone-cone {
        fill: var(--ha-color-fill-neutral-loud-resting);
        fill-opacity: 0.12;
        stroke: var(--ha-color-border-neutral-normal);
        stroke-dasharray: 4 4;
      }
      .map .cyclone-buffer-green {
        fill: var(--ha-color-fill-warning-loud-resting);
        fill-opacity: 0.15;
        stroke: var(--ha-color-border-warning-normal);
      }
      .map .cyclone-buffer-orange {
        fill: var(--ha-color-fill-warning-loud-resting);
        fill-opacity: 0.3;
        stroke: var(--ha-color-border-warning-loud);
      }
      .map .cyclone-buffer-red {
        fill: var(--ha-color-fill-danger-loud-resting);
        fill-opacity: 0.35;
        stroke: var(--ha-color-border-danger-loud);
      }
      .map .cyclone-track,
      .map .cyclone-track-forecast {
        fill: none;
        stroke: var(--ha-color-border-danger-loud);
        stroke-opacity: 1;
      }
      .map .cyclone-track-forecast {
        stroke-dasharray: 6 4;
      }
    `];titleKey=`map.title`;static defaultArea=`radius`;usesIncidents=!0;_map;_container;_creating=!1;_resizeObserver;_intersectionObserver;_reducedMotion=typeof matchMedia==`function`&&matchMedia(`(prefers-reduced-motion: reduce)`).matches;constructor(){super(),this._status=or,this._loadError=!1,this._satelliteHidden=!1,this._cyclonesHidden=!1,this._viirsDay=ir(Date.now())}static validateConfig(e){super.validateConfig(e);let t=e;$(t,`zoom`,1,18),Gt(t,`radar`),Wt(t,`radar_opacity`,.1,1),Kt(t,`satellite_layer`,Ln),Gt(t,`show_cyclone_tracks`)}static getConfigForm(){return{schema:[...X(),Y(this.defaultArea),{name:`zoom`,selector:{number:{min:1,max:18,mode:`box`}}},{name:`radar`,default:!0,selector:{boolean:{}}},{name:`radar_opacity`,visible:{field:`radar`,operator:`not_eq`,value:!1},selector:{number:{min:.1,max:1,step:.05,mode:`slider`}}},{name:`satellite_layer`,default:`none`,selector:{select:{mode:`dropdown`,options:Ln.map(e=>({value:e,label:f(void 0,vr(e))}))}}},{name:`show_cyclone_tracks`,default:!1,selector:{boolean:{}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getGridOptions(){return{columns:12,rows:6,min_columns:6,min_rows:4}}getCardSize(){return 7}trackedHomeId=`zone.home`;trackedEntityIds(e){let t=[...super.trackedEntityIds(e),this.trackedHomeId],n=this._config?.show_cyclone_tracks?this.alertsEntityId(e):void 0;return n&&t.push(n),t}alertsEntityId(e){return St(e,this.deviceId,n.regionalDisasterAlerts)}connectedCallback(){super.connectedCallback(),this.hasUpdated&&this.ensureMap()}disconnectedCallback(){super.disconnectedCallback(),this.teardown()}teardown(){this._resizeObserver?.disconnect(),this._intersectionObserver?.disconnect(),this._resizeObserver=void 0,this._intersectionObserver=void 0,this._map?.destroy(),this._map=void 0,this._container=void 0}updated(e){super.updated(e),this._map&&this.renderRoot.querySelector(`.map`)!==this._container&&this.teardown(),this._map?(e.has(`hass`)||mr.some(t=>e.has(t)))&&this._map.update(this.viewOptions()):this.ensureMap()}viewOptions(){let e=this.hass,t=this.areaFilter(e),n=Tt(e,this.entryId).flatMap(n=>{if(!t.keep(n.attributes.in_council_area))return[];let r=F(n.attributes.latitude),i=F(n.attributes.longitude);if(r===void 0||i===void 0)return[];let a=K(n.attributes.warning_level);return[{id:n.entity_id,title:Et(n),levelLabel:f(e,xn[a.level]),tone:a.tone,latitude:r,longitude:i,agency:I(n.attributes.responsible_agency)??I(n.attributes.agency)}]}),r=e.states[this.trackedHomeId],i=F(r?.attributes.latitude),a=F(r?.attributes.longitude),o=i!==void 0&&a!==void 0?{latitude:i,longitude:a,radius:F(r?.attributes.radius),label:f(e,`map.home`)}:Number.isFinite(e.config?.latitude)&&Number.isFinite(e.config?.longitude)?{latitude:e.config.latitude,longitude:e.config.longitude,label:f(e,`map.home`)}:void 0,s=this._config?.satellite_layer??`none`,c=this._config?.show_cyclone_tracks&&!this._cyclonesHidden?this.alertsEntityId(e):void 0;return{incidents:n,home:o,darkMode:!!e.themes?.darkMode,zoom:this._config?.zoom,radar:this._config?.radar!==!1,radarOpacity:this._config?.radar_opacity??pr,satellite:this._satelliteHidden?`none`:s,viirsDay:this._viirsDay,cyclones:c?Dn(e.states[c]?.attributes.alerts):[]}}async ensureMap(){if(this._map||this._creating||!this.hass||!this.isConnected)return;let e=this.renderRoot.querySelector(`.map`);if(e){this._creating=!0;try{let t=await gr(),n=this.renderRoot;if(!n.adoptedStyleSheets.some(e=>e.leaflet)){let e=new CSSStyleSheet;e.replaceSync(t.leafletCss),e.leaflet=!0,n.adoptedStyleSheets=[e,...n.adoptedStyleSheets]}if(!this.isConnected||this._map||!e.isConnected)return;this._container=e,this._map=new t.IncidentMap(e,this.hass.connection,e=>this._status=e,e=>this.moreInfo(e),this._reducedMotion),this._resizeObserver=new ResizeObserver(()=>this._map?.invalidateSize()),this._resizeObserver.observe(e),this._intersectionObserver=new IntersectionObserver(e=>this._map?.setVisible(e.some(e=>e.isIntersecting))),this._intersectionObserver.observe(this),this._map.update(this.viewOptions())}catch(e){console.error(`Disaster Watch map failed to load`,e),this._loadError=!0}finally{this._creating=!1}}}togglePlay(){let e=!this._status.frame?.playing;this._map?.setPlaying(e)}renderRadarBar(e){let t=this._status.frame;if(!t)return O;let n=ut(e,t.time,{timeStyle:`short`}),r=lt(e,t.time),i=t.playing,a=t.source===`radar`,o=a?f(e,i?`map.pause`:`map.play`):f(e,i?`map.pause_satellite`:`map.play_satellite`),s=f(e,a?`map.radar_at`:`map.satellite_at`,{time:n??``});return E`<div class="radar-bar">
      <ha-icon-button .label=${o} aria-pressed=${i?`true`:`false`} @click=${this.togglePlay}>
        <ha-icon .icon=${i?`mdi:pause`:`mdi:play`}></ha-icon>
      </ha-icon-button>
      <span class="time" aria-live=${i?`off`:`polite`}>${s}${r?` · ${r}`:``}</span>
      <span class="frames" aria-hidden="true">
        ${Array.from({length:t.count},(e,n)=>E`<span class=${n===t.index?`current`:``}></span>`)}
      </span>
    </div>`}renderLayerChips(e,t){let n=t.satellite_layer??`none`;if(n===`none`&&!t.show_cyclone_tracks)return O;let r=n===`viirs_truecolor`&&!this._satelliteHidden,i=new Intl.DateTimeFormat(nt(e),{day:`numeric`,month:`short`,timeZone:`UTC`}),a=Date.now();return E`<div class="layers">
      <ha-chip-set aria-label=${f(e,`map.layers`)}>
        ${n===`none`?O:E`<ha-filter-chip
                .selected=${!this._satelliteHidden}
                .label=${f(e,vr(n))}
                @click=${e=>{e.preventDefault(),this._satelliteHidden=!this._satelliteHidden}}
              >
                <ha-icon slot="icon" icon="mdi:satellite-variant"></ha-icon>
              </ha-filter-chip>`}
        ${r?rr.map(t=>{let n=i.format(Date.parse(ar(a,t)));return E`<ha-filter-chip
        no-leading-icon
        .selected=${this._viirsDay===t}
        .label=${n}
        title=${`${f(e,`map.viirs_days`)}: ${n}`}
        @click=${e=>{e.preventDefault(),this._viirsDay=t}}
      ></ha-filter-chip>`}):O}
        ${t.show_cyclone_tracks?E`<ha-filter-chip
                .selected=${!this._cyclonesHidden}
                .label=${f(e,`map.cyclones`)}
                @click=${e=>{e.preventDefault(),this._cyclonesHidden=!this._cyclonesHidden}}
              >
                <ha-icon slot="icon" icon="mdi:weather-hurricane"></ha-icon>
              </ha-filter-chip>`:O}
      </ha-chip-set>
    </div>`}renderNotices(e){let t=this._status,n=t=>E`<div class="notice">${B(`info`,f(e,t))}</div>`,r=[];return t.radar===`unavailable`&&r.push(n(`map.radar_unavailable`)),t.satellite===`unavailable`&&r.push(n(`map.satellite_unavailable`)),t.cyclones===`unavailable`&&r.push(n(`map.cyclones_unavailable`)),this.areaFilter(e).fallback&&r.push(n(`area.fallback`)),r}renderBody(e,t){let n=xt(e,this.deviceId)??e.config?.location_name??``;return E`${V({title:this.cardTitle(),icon:`mdi:map-marker-radius`,subtitle:this.areaFilter(e).council?.name})}
      <div class="map-wrap">
        <div class="map" role="region" aria-label=${f(e,`map.label`,{name:n})}></div>
      </div>
      ${this.renderLayerChips(e,t)}
      ${this.renderRadarBar(e)}
      ${this._status.cyclones===`ok`&&this._status.cycloneCount>0?E`<p class="legend">${f(e,`map.cyclone_legend`)}</p>`:O}
      ${this.renderNotices(e)}
      ${this._loadError?E`<div class="notice">${B(`error`,f(e,`state.unavailable`))}</div>`:O}`}};function vr(e){return e===`none`?`editor.satellite_layer.none`:`map.layer.${e}`}function yr(e,t){return(M(e)?void 0:F(e?.state))??F(t)}var br=8,xr=class extends q{static properties={...q.properties,_expanded:{state:!0}};titleKey=`outages.title`;static defaultArea=`council`;constructor(){super(),this._expanded=!1}entityKeys(){return[n.powerOutagesCount,n.powerOutagesCustomersAffected]}static validateConfig(e){super.validateConfig(e),$(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...X(),Y(this.defaultArea),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}renderBody(e,t){let r=G(e,this.deviceId,n.powerOutagesCount),i=this.areaFilter(e),a=V({title:this.cardTitle(),icon:`mdi:transmission-tower-off`,subtitle:i.council?.name,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(M(r))return E`${a}<div class="content">
          ${B(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let o=L(r.attributes.outages).filter(e=>i.keep(e.in_council_area)),s=(i.council?F(r.attributes.council_area_count):F(r.state))??o.length,c=i.council?F(r.attributes.council_area_customers_affected):yr(G(e,this.deviceId,n.powerOutagesCustomersAffected),r.attributes.customers_affected),l=t.max_items??br,u=this._expanded?o:o.slice(0,l);return E`${a}
      <div class="content">
        ${this.areaHint(e,i)}
        ${s===0?z(`mdi:transmission-tower`,f(e,`outages.empty`)):E`<span class="secondary"
                  >${[m(e,`outages.count`,s,N(e,s)),c===void 0?void 0:m(e,`outages.customers_affected`,c,N(e,c))].filter(Boolean).join(` · `)}</span
                >
                ${U(u.map(t=>{let n=ut(e,t.restore_time,{weekday:`short`,hour:`numeric`,minute:`2-digit`})??I(t.restore_time),r=F(t.customers_affected);return H({icon:`mdi:transmission-tower-off`,tone:`amber`,headline:I(t.suburb)??`—`,supporting:[I(t.cause),n?f(e,`outages.restore`,{time:n}):void 0].filter(Boolean).join(` · `)||void 0,trailing:r===void 0?void 0:E`<span class="secondary"
                              >${m(e,`outages.customers`,r,N(e,r))}</span
                            >`})}),this.cardTitle())}
                ${o.length>l?ht(e,this._expanded,o.length,()=>this._expanded=!this._expanded):O}`}
      </div>`}};function Sr(e){if(!e||typeof e!=`object`)return;let t=e,n=dt(t.url),r=I(t.name)??I(t.url);return r?{name:r,url:n}:void 0}function Cr(e,t){let n=e=>e?.replace(/^https?:\/\//i,``).replace(/\/+$/,``).toLowerCase();return!!e&&!!t&&n(e)===n(t)}function wr(e,t,n){let r=Sr(e);return{own:r,nearby:n?L(t).map(Sr).filter(e=>!!e&&!(r&&Cr(e.url,r.url))):[]}}var Tr=[{key:`evacuation_centre`,icon:`mdi:home-group`},{key:`place_of_refuge`,icon:`mdi:home-heart`},{key:`sandbag_station`,icon:`mdi:sack`},{key:`other`,icon:`mdi:home-alert`}];function Er(e){return e===`evacuation_centre`||e===`place_of_refuge`||e===`sandbag_station`?e:`other`}function Dr(e,t){return t.map(t=>H({icon:`mdi:view-dashboard-outline`,tone:`blue`,headline:t.name,supporting:t.url?new URL(t.url).hostname:void 0,link:t.url,linkLabel:`${f(e,`action.open_link`)}: ${t.name}`}))}var Or=class extends q{titleKey=`relief.title`;static defaultArea=`council`;entityKeys(){return[n.reliefFacilitiesCount,n.highestWarningLevel,n.weatherWarningsCount]}static validateConfig(e){super.validateConfig(e),Gt(e,`show_nearby_councils`)}static getConfigForm(){return{schema:[...X(),Y(this.defaultArea),{name:`show_nearby_councils`,selector:{boolean:{}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getCardSize(){return 5}renderBody(e,t){let r=G(e,this.deviceId,n.reliefFacilitiesCount),i=G(e,this.deviceId,n.highestWarningLevel),a=G(e,this.deviceId,n.weatherWarningsCount),o=this.areaFilter(e),s=V({title:this.cardTitle(),icon:`mdi:home-heart`,subtitle:o.council?.name,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(M(r))return E`${s}<div class="content">
          ${B(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let c=L(r.attributes.facilities).filter(e=>o.keep(e.in_council_area)).sort((e,t)=>(F(e.distance_km)??1/0)-(F(t.distance_km)??1/0)),l=wr(i?.attributes.council??a?.attributes.council,i?.attributes.nearby_councils??a?.attributes.nearby_councils,t.show_nearby_councils??!1);return E`${s}
      <div class="content">
        ${this.areaHint(e,o)}
        ${c.length===0?z(`mdi:home-search-outline`,f(e,`relief.empty`)):O}
        ${Tr.map(({key:t,icon:n})=>{let r=c.filter(e=>Er(e.facility_type)===t);if(!r.length)return O;let i=f(e,`relief.group.${t}`);return E`<h3 class="list-title">${i}</h3>
            ${U(r.map(t=>{let r=(I(t.status)??`Open`).toLowerCase()!==`closed`,a=I(t.name)??i;return H({icon:n,tone:r?`green`:`grey`,headline:a,supporting:I(t.address)??I(t.suburb),badge:R(f(e,r?`relief.open`:`relief.closed`),r?`green`:`grey`,r?`mdi:door-open`:`mdi:door-closed`),trailing:P(e,F(t.distance_km))})}),i)}`})}
        ${l.own?E`<h3 class="list-title">${f(e,`relief.own_council`)}</h3>
                ${U(Dr(e,[l.own]),f(e,`relief.own_council`))}`:O}
        ${l.nearby.length?E`<h3 class="list-title">${f(e,`relief.councils`)}</h3>
                ${U(Dr(e,l.nearby),f(e,`relief.councils`))}`:O}
      </div>`}},kr=8,Ar=class extends q{static properties={...q.properties,_expanded:{state:!0}};titleKey=`roads.title`;static defaultArea=`council`;constructor(){super(),this._expanded=!1}entityKeys(){return[n.roadClosuresCount]}static validateConfig(e){super.validateConfig(e),$(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...X(),Y(this.defaultArea),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}renderBody(e,t){let r=G(e,this.deviceId,n.roadClosuresCount),i=M(r),a=this.areaFilter(e),o=i?[]:L(r.attributes.closures).filter(e=>a.keep(e.in_council_area)),s=a.council?F(r?.attributes.council_area_count):F(r?.state),c=i?void 0:s??o.length,l=V({title:this.cardTitle(),icon:`mdi:traffic-cone`,subtitle:a.council?.name,count:c?N(e,c):void 0,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(i)return E`${l}<div class="content">
          ${B(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let u=[...o].sort((e,t)=>(F(e.distance_km)??1/0)-(F(t.distance_km)??1/0)),d=t.max_items??kr,p=this._expanded?u:u.slice(0,d);return E`${l}
      <div class="content">
        ${this.areaHint(e,a)}
        ${u.length?U(p.map(t=>{let n=I(t.status)??`—`,r=cn(n),i=lt(e,t.updated_at);return H({icon:ln(n),tone:r,headline:[I(t.road),I(t.suburb)].filter(Boolean).join(`, `)||n,supporting:[I(t.advice)??I(t.description)??I(t.reason),i].filter(Boolean).join(` · `)||void 0,badge:R(n,r),trailing:P(e,F(t.distance_km))})}),this.cardTitle()):z(`mdi:road-variant`,f(e,`roads.empty`))}
        ${u.length>d?ht(e,this._expanded,u.length,()=>this._expanded=!this._expanded):O}
      </div>`}},jr=[{key:n.emergencyWarningNearby,icon:`mdi:alert-octagon`,label:`status.chip.emergency_warning_nearby`},{key:n.activeHazardsNearby,icon:`mdi:alert`,label:`status.chip.active_hazards_nearby`},{key:n.powerOutageActive,icon:`mdi:transmission-tower-off`,label:`status.chip.power_outage_active`},{key:n.roadClosureNearby,icon:`mdi:traffic-cone`,label:`status.chip.road_closure_nearby`}],Mr=new Set([`all_clear`,`emergency`,`watch_and_act`,`advice`,`information`]),Nr={all_clear:`status.all_clear`,unavailable:`status.unavailable`,emergency:`status.level.emergency`,watch_and_act:`status.level.watch_and_act`,advice:`status.level.advice`,information:`status.level.information`,unknown:`status.level.unknown`},Pr=class extends q{static styles=[...q.styles,y`
      .hero {
        display: flex;
        align-items: center;
        gap: var(--ha-space-4);
        padding: var(--ha-space-2);
        margin: calc(-1 * var(--ha-space-2));
        width: calc(100% + 2 * var(--ha-space-2));
      }
      .hero:hover {
        background-color: var(--ha-color-fill-neutral-quiet-hover);
      }
      .hero-text {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-1);
        min-width: 0;
      }
      .level {
        font-family: var(--ha-font-family-heading);
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-bold);
        line-height: var(--ha-line-height-condensed);
      }
      .summary {
        color: var(--secondary-text-color);
        font-size: var(--ha-font-size-m);
        line-height: var(--ha-line-height-normal);
      }
      .nearest {
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
      }
      .content.status {
        padding-top: var(--ha-space-4);
      }
    `];titleKey=`card.status.name`;static defaultArea=`radius`;usesIncidents=!0;entityKeys(){return[n.highestWarningLevel,n.activeHazardsCount,n.nearestHazardDistance,n.nearestHazardTitle,...jr.map(e=>e.key)]}static getConfigForm(){return{schema:[...X(),Y(this.defaultArea)],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}getCardSize(){return 2}renderBody(e,t){let r=this.deviceId,i=G(e,r,n.highestWarningLevel),a=this.areaFilter(e),o=a.council&&i&&i.state!==`unavailable`?Vt(Tt(e,this.entryId).filter(e=>a.keep(e.attributes.in_council_area)).map(e=>({level:e.attributes.warning_level,distanceKm:Dt(e),title:Et(e)}))):void 0,s=G(e,r,n.activeHazardsCount),c=o?o.count:M(s)?void 0:F(s?.state),l=It(o?o.level:i?.state,c),u=Lt(l),d=!o&&i&&e.formatEntityState&&Mr.has(l)?e.formatEntityState(i):f(e,Nr[l]),p=G(e,r,n.nearestHazardDistance),m=G(e,r,n.nearestHazardTitle),h=o?o.nearestKm:M(p)?void 0:F(p?.state),g=o?o.nearestTitle:I(p?.attributes.title)??(M(m)||m?.state===`None`?void 0:I(m?.state)),_=``;if(l!==`unavailable`&&c!==void 0){let t=a.council?.name??``;_=o?c===0?f(e,`status.no_hazards_council`,{name:t}):c===1?f(e,`status.hazard_council`,{name:t}):f(e,`status.hazards_council`,{count:N(e,c),name:t}):c===0?f(e,`status.no_hazards`):c===1?f(e,`status.hazard`):f(e,`status.hazards`,{count:N(e,c)})}let ee=P(e,h),v=c&&ee?`${f(e,`status.nearest`,{distance:ee})}${g?` — ${g}`:``}`:void 0,te=jr.map(t=>({...t,stateObj:G(e,r,t.key)})).filter(e=>e.stateObj?.state===`on`);return E`<div class="content status">
      ${this.areaHint(e,a)}
      <button
        class="plain hero"
        aria-label=${`${d}. ${_}${v?`, ${v}`:``}. ${f(e,`action.details`)}`}
        @click=${()=>this.moreInfo(i?.entity_id)}
      >
        <span class="bubble large" style=${et({"--tone":ft(u.tone)})} aria-hidden="true">
          <ha-icon .icon=${u.icon}></ha-icon>
        </span>
        <span class="hero-text">
          <span class="level">${d}</span>
          ${_?E`<span class="summary">${_}</span>`:O}
          ${v?E`<span class="summary nearest">${v}</span>`:O}
        </span>
      </button>
      ${te.length?E`<ha-chip-set aria-label=${f(e,`status.alerts`)}>
              ${te.map(t=>E`<ha-assist-chip
                  filled
                  .label=${f(e,t.label)}
                  @click=${()=>this.moreInfo(t.stateObj?.entity_id)}
                >
                  <ha-icon slot="icon" .icon=${t.icon}></ha-icon>
                </ha-assist-chip>`)}
            </ha-chip-set>`:O}
    </div>`}},Fr=8,Ir={status:Pr,incidents:Sn,warnings:class extends q{static properties={...q.properties,_view:{state:!0},_expanded:{state:!0}};titleKey=`warnings.title`;constructor(){super(),this._view=`warnings`,this._expanded=!1}entityKeys(){return[n.weatherWarningsCount,n.highestWarningLevel]}static validateConfig(e){super.validateConfig(e),$(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...X(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:Z,computeHelper:Q,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return J(e)}getCardSize(){return 5}renderItem(e,t,n){let r=I(t.title)??``,i=lt(e,t.pub_date),a=I(t.locations)??I(t.description);return H({icon:n,tone:this._view===`warnings`?`orange`:`blue`,headline:r,supporting:[a,i].filter(Boolean).join(` · `)||void 0,link:dt(t.link),linkLabel:`${f(e,`action.open_link`)}: ${r}`})}renderBody(e,t){let r=G(e,this.deviceId,n.weatherWarningsCount),i=G(e,this.deviceId,n.highestWarningLevel),a=M(r),o=L(r?.attributes.warnings),s=L(r?.attributes.emergency_news??i?.attributes.emergency_news),c=a?0:F(r?.state)??o.length,l=this._view===`warnings`?o:s,u=t.max_items??Fr,d=this._expanded?l:l.slice(0,u),p=this._view===`warnings`?`mdi:weather-lightning-rainy`:`mdi:newspaper-variant-outline`,m=(e,t)=>E`<ha-filter-chip
      no-leading-icon
      .selected=${this._view===e}
      .label=${t}
      @click=${t=>{t.preventDefault(),this._view=e,this._expanded=!1}}
    ></ha-filter-chip>`;return E`${V({title:this.cardTitle(),icon:`mdi:weather-lightning-rainy`,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0})}
      <div class="content">
        ${a?B(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`)):E`<ha-chip-set aria-label=${f(e,`warnings.views`)}>
                  ${m(`warnings`,f(e,`warnings.tab.warnings`,{count:N(e,c)}))}
                  ${m(`news`,f(e,`warnings.tab.news`,{count:N(e,s.length)}))}
                </ha-chip-set>
                ${d.length?U(d.map(t=>this.renderItem(e,t,p))):z(`mdi:check-circle-outline`,f(e,this._view===`warnings`?`warnings.empty`:`warnings.news_empty`))}
                ${l.length>u?ht(e,this._expanded,l.length,()=>this._expanded=!this._expanded):O}
`}
      </div>`}},fire_danger:mn,outages:xr,roads:Ar,conditions:pn,relief:Or,cameras:Qt,map:_r},Lr=[{tag:i,ctor:Yt,key:`all`},...Object.keys(Ir).map(e=>({tag:r[e],ctor:Ir[e],key:e}))];window.customCards=window.customCards||[];for(let{tag:e,ctor:n,key:r}of Lr)customElements.get(e)||customElements.define(e,n),window.customCards.some(t=>t.type===e)||window.customCards.push({type:e,name:f(void 0,`card.${r}.name`),description:f(void 0,`card.${r}.description`),preview:!0,documentationURL:t});export{qn as a,Fn as c,Xn as i,Vn as n,ar as o,nr as r,Cn as s,or as t};
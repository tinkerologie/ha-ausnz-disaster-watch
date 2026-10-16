var e=`ausnz_disaster_watch`,t=`https://github.com/tinkerologie/ha-ausnz-disaster-watch#dashboard-cards`,n={emergencyWarningNearby:`emergency_warning_nearby`,activeHazardsNearby:`active_hazards_nearby`,powerOutageActive:`power_outage_active`,roadClosureNearby:`road_closure_nearby`,nearestHazardDistance:`nearest_hazard_distance`,activeHazardsCount:`active_hazards_count`,highestWarningLevel:`highest_warning_level`,nearestHazardTitle:`nearest_hazard_title`,powerOutagesCount:`power_outages_count`,powerOutagesCustomersAffected:`power_outages_customers_affected`,roadClosuresCount:`road_closures_count`,weatherWarningsCount:`weather_warnings_count`,fireDangerRating:`fire_danger_rating`,airQualityRating:`air_quality_rating`,primaryWeatherObservation:`primary_weather_observation`,reliefFacilitiesCount:`relief_facilities_count`,regionalDisasterAlerts:`regional_disaster_alerts`},r={status:`ausnz-disaster-status-card`,incidents:`ausnz-disaster-incidents-card`,warnings:`ausnz-disaster-warnings-card`,fire_danger:`ausnz-disaster-fire-danger-card`,outages:`ausnz-disaster-outages-card`,roads:`ausnz-disaster-roads-card`,conditions:`ausnz-disaster-conditions-card`,relief:`ausnz-disaster-relief-card`,cameras:`ausnz-disaster-cameras-card`,map:`ausnz-disaster-map-card`},i=`ausnz-disaster-card`,a=[`status`,`incidents`,`warnings`,`fire_danger`,`roads`,`outages`],o=Object.keys(r),s={"card.status.name":`Disaster Watch status`,"card.status.description":`Headline warning level, hazard count, nearest hazard and active alerts.`,"card.incidents.name":`Disaster Watch incidents`,"card.incidents.description":`Incidents nearest first, with category filters and Australian Warning System levels.`,"card.warnings.name":`Disaster Watch warnings`,"card.warnings.description":`Weather warnings and emergency news.`,"card.fire_danger.name":`Disaster Watch fire danger`,"card.fire_danger.description":`Fire danger rating on the AFDRS scale, district and total fire ban.`,"card.outages.name":`Disaster Watch power outages`,"card.outages.description":`Power outages and customers affected.`,"card.roads.name":`Disaster Watch roads`,"card.roads.description":`Road closures and hazards.`,"card.conditions.name":`Disaster Watch conditions`,"card.conditions.description":`Local weather observation and air quality.`,"card.relief.name":`Disaster Watch relief`,"card.relief.description":`Evacuation centres, places of refuge, sandbag stations and council dashboards.`,"card.cameras.name":`Disaster Watch cameras`,"card.cameras.description":`Flood and traffic camera snapshots.`,"card.map.name":`Disaster Watch map`,"card.map.description":`Map of incidents with animated rain radar.`,"card.all.name":`Disaster Watch`,"card.all.description":`All-in-one card: a configurable stack of the Disaster Watch cards.`,"state.not_set_up":`Set up the Australia and New Zealand Disaster Watch integration to use this card.`,"state.device_missing":`The selected Disaster Watch device was not found. Choose another device in the card editor.`,"state.unavailable":`Data is unavailable right now.`,"state.entity_missing":`This Disaster Watch entity is missing or disabled.`,"action.details":`Show details`,"action.open_link":`Open source page`,"action.show_all":`Show all {count}`,"action.show_less":`Show less`,"status.all_clear":`All clear`,"status.unavailable":`Status unavailable`,"status.level.emergency":`Emergency Warning`,"status.level.watch_and_act":`Watch and Act`,"status.level.advice":`Advice`,"status.level.information":`Information`,"status.level.unknown":`Level unknown`,"status.hazards":`{count} hazards nearby`,"status.hazard":`1 hazard nearby`,"status.no_hazards":`No hazards nearby`,"status.nearest":`nearest {distance}`,"status.chip.emergency_warning_nearby":`Emergency warning`,"status.chip.active_hazards_nearby":`Hazards nearby`,"status.chip.power_outage_active":`Power outage`,"status.chip.road_closure_nearby":`Road closure`,"status.alerts":`Active alerts`,"incidents.title":`Incidents`,"incidents.empty":`No incidents nearby.`,"incidents.empty_filtered":`No incidents in this category.`,"incidents.filters":`Incident filters`,"incidents.category.all":`All`,"incidents.category.fire":`Fire`,"incidents.category.flood_storm":`Flood & storm`,"incidents.category.geological":`Geological`,"incidents.category.roads":`Roads`,"incidents.category.other":`Other`,"incidents.planned_burns":`Planned burns`,"incidents.planned_burn":`Planned burn`,"incidents.updated":`updated {time}`,"warnings.title":`Warnings`,"warnings.tab.warnings":`Warnings ({count})`,"warnings.tab.news":`News ({count})`,"warnings.views":`Warnings or news`,"warnings.empty":`No weather warnings.`,"warnings.news_empty":`No emergency news.`,"fire.title":`Fire danger`,"fire.rating.moderate":`Moderate`,"fire.rating.high":`High`,"fire.rating.extreme":`Extreme`,"fire.rating.catastrophic":`Catastrophic`,"fire.rating.no_rating":`No rating`,"fire.scale":`Fire danger rating scale`,"fire.current":`Current rating`,"fire.forecast_for":`Forecast for {day}`,"fire.total_fire_ban":`Total fire ban`,"fire.no_total_fire_ban":`No total fire ban`,"fire.district":`{district} district`,"outages.title":`Power outages`,"outages.count":`{count} outages`,"outages.count_one":`{count} outage`,"outages.customers_affected":`{count} customers affected`,"outages.customers_affected_one":`{count} customer affected`,"outages.empty":`No power outages reported.`,"outages.customers":`{count} customers`,"outages.customers_one":`{count} customer`,"outages.restore":`Restore {time}`,"roads.title":`Roads`,"roads.empty":`No road closures or hazards.`,"conditions.title":`Conditions`,"conditions.weather":`Weather`,"conditions.air_quality":`Air quality`,"conditions.temperature":`Temperature`,"conditions.feels_like":`Feels like`,"conditions.humidity":`Humidity`,"conditions.wind":`Wind`,"conditions.wind_from":`Wind from {direction}`,"conditions.gust":`Gust`,"conditions.pressure":`Pressure`,"conditions.rain":`Rain since 9 am`,"conditions.station":`Station: {name}`,"conditions.no_weather":`No weather observation.`,"conditions.no_air_quality":`No air quality reading.`,"conditions.aq.good":`Good`,"conditions.aq.fair":`Fair`,"conditions.aq.poor":`Poor`,"conditions.aq.very_poor":`Very poor`,"conditions.aq.extremely_poor":`Extremely poor`,"conditions.aq.unknown":`Unknown`,"relief.title":`Relief`,"relief.empty":`No relief facilities open nearby.`,"relief.group.evacuation_centre":`Evacuation centres`,"relief.group.place_of_refuge":`Places of refuge`,"relief.group.sandbag_station":`Sandbag stations`,"relief.group.other":`Other facilities`,"relief.councils":`Council dashboards`,"relief.open":`Open`,"relief.closed":`Closed`,"cameras.title":`Cameras`,"cameras.empty":`No cameras for this location.`,"cameras.no_image":`No image yet`,"map.title":`Map`,"map.label":`Map of incidents near {name}`,"map.home":`Home`,"map.play":`Play radar animation`,"map.pause":`Pause radar animation`,"map.radar_at":`Radar {time}`,"map.radar_unavailable":`Rain radar is unavailable right now.`,"map.radar_off":`Radar off`,"map.play_satellite":`Play satellite animation`,"map.pause_satellite":`Pause satellite animation`,"map.satellite_at":`Satellite {time}`,"map.satellite_unavailable":`Satellite imagery is unavailable right now.`,"map.layers":`Map layers`,"map.layer.himawari_visible":`Himawari visible`,"map.layer.himawari_ir":`Himawari infrared`,"map.layer.viirs_truecolor":`VIIRS true colour`,"map.viirs_days":`VIIRS image date`,"map.cyclones":`Cyclone tracks`,"map.cyclones_unavailable":`Cyclone tracks are unavailable right now.`,"map.cyclone_legend":`GDACS model estimate — follow BoM / MetService warnings.`,"editor.device":`Disaster Watch location`,"editor.device_helper":`The integration entry (location) this card shows. Defaults to the first one.`,"editor.title":`Title`,"editor.title_helper":`Leave empty for the default title.`,"editor.max_items":`Maximum items`,"editor.max_items_helper":`Rows shown before a Show all button.`,"editor.show_planned_burns":`Show planned burns`,"editor.show_planned_burns_helper":`Planned burns only reach the card when the integration's 'Exclude hazard reduction burns' option is off.`,"editor.categories":`Categories`,"editor.categories_helper":`Incident categories to show. Leave empty for all.`,"editor.refresh_interval":`Refresh interval`,"editor.refresh_interval_helper":`Seconds between snapshot refreshes while the card is visible.`,"editor.zoom":`Zoom`,"editor.zoom_helper":`Initial zoom. Leave empty to fit all incidents.`,"editor.radar":`Rain radar`,"editor.radar_helper":`Animated RainViewer radar (free for personal use, attribution shown on the map).`,"editor.radar_opacity":`Radar opacity`,"editor.satellite_layer":`Satellite layer`,"editor.satellite_layer_helper":`Himawari clouds (every 10 minutes; visible is daytime only, infrared day and night) or the daily VIIRS true colour image (smoke, burn scars, flood extent). Imagery from NASA GIBS.`,"editor.satellite_layer.none":`None`,"editor.show_cyclone_tracks":`Cyclone tracks`,"editor.show_cyclone_tracks_helper":`Draw GDACS forecast tracks and wind areas of current cyclones listed by the Regional Disaster Alerts sensor (turn on 'Regional disaster alerts (GDACS)' in the integration options). Model estimates only: follow BoM and MetService warnings.`,"editor.cards":`Sections`,"editor.cards_helper":`Cards to stack, in order.`},c={en:s};function l(e){let t=e?.locale?.language||e?.language||`en`;if(c[t])return{lang:t,strings:c[t]};let n=t.split(`-`)[0]??`en`;return c[n]?{lang:n,strings:c[n]}:{lang:`en`,strings:s}}function u(e,t){let n=l(e);return n.strings[t]===void 0?{lang:`en`,strings:s,template:s[t]}:{...n,template:n.strings[t]}}function d(e,t){return t?e.replace(/\{(\w+)\}/g,(e,n)=>n in t?String(t[n]):e):e}function f(e,t,n){return d(u(e,t).template??t,n)}function ee(e,t){try{return new Intl.PluralRules(e).select(t)}catch{return t===1?`one`:`other`}}function p(e,t,n,r=String(n)){let{lang:i,strings:a,template:o}=u(e,t),s=a[`${t}_one`];return d(ee(i,n)===`one`&&s!==void 0?s:o??t,{count:r})}var m=globalThis,h=m.ShadowRoot&&(m.ShadyCSS===void 0||m.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,g=Symbol(),te=new WeakMap,ne=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==g)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(h&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=te.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&te.set(t,e))}return e}toString(){return this.cssText}},re=e=>new ne(typeof e==`string`?e:e+``,void 0,g),_=(e,...t)=>new ne(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,g),ie=(e,t)=>{if(h)e.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let n of t){let t=document.createElement(`style`),r=m.litNonce;r!==void 0&&t.setAttribute(`nonce`,r),t.textContent=n.cssText,e.appendChild(t)}},ae=h?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return re(t)})(e):e,{is:oe,defineProperty:se,getOwnPropertyDescriptor:ce,getOwnPropertyNames:le,getOwnPropertySymbols:ue,getPrototypeOf:de}=Object,v=globalThis,fe=v.trustedTypes,pe=fe?fe.emptyScript:``,me=v.reactiveElementPolyfillSupport,y=(e,t)=>e,he={toAttribute(e,t){switch(t){case Boolean:e=e?pe:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},ge=(e,t)=>!oe(e,t),_e={attribute:!0,type:String,converter:he,reflect:!1,useDefault:!1,hasChanged:ge};Symbol.metadata??=Symbol(`metadata`),v.litPropertyMetadata??=new WeakMap;var b=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=_e){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&se(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=ce(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??_e}static _$Ei(){if(this.hasOwnProperty(y(`elementProperties`)))return;let e=de(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(y(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(y(`properties`))){let e=this.properties,t=[...le(e),...ue(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(ae(e))}else e!==void 0&&t.push(ae(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ie(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?he:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?he:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??ge)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};b.elementStyles=[],b.shadowRootOptions={mode:`open`},b[y(`elementProperties`)]=new Map,b[y(`finalized`)]=new Map,me?.({ReactiveElement:b}),(v.reactiveElementVersions??=[]).push(`2.1.2`);var ve=globalThis,ye=e=>e,be=ve.trustedTypes,xe=be?be.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,Se=`$lit$`,x=`lit$${Math.random().toFixed(9).slice(2)}$`,Ce=`?`+x,we=`<${Ce}>`,S=document,C=()=>S.createComment(``),w=e=>e===null||typeof e!=`object`&&typeof e!=`function`,Te=Array.isArray,Ee=e=>Te(e)||typeof e?.[Symbol.iterator]==`function`,De=`[ 	
\f\r]`,T=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Oe=/-->/g,ke=/>/g,E=RegExp(`>|${De}(?:([^\\s"'>=/]+)(${De}*=${De}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),Ae=/'/g,je=/"/g,Me=/^(?:script|style|textarea|title)$/i,D=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),O=Symbol.for(`lit-noChange`),k=Symbol.for(`lit-nothing`),Ne=new WeakMap,A=S.createTreeWalker(S,129);function Pe(e,t){if(!Te(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return xe===void 0?t:xe.createHTML(t)}var Fe=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=T;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===T?c[1]===`!--`?o=Oe:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=E):(Me.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=E):o=ke:o===E?c[0]===`>`?(o=i??T,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?E:c[3]===`"`?je:Ae):o===je||o===Ae?o=E:o===Oe||o===ke?o=T:(o=E,i=void 0);let d=o===E&&e[t+1].startsWith(`/>`)?` `:``;a+=o===T?n+we:l>=0?(r.push(s),n.slice(0,l)+Se+n.slice(l)+x+d):n+x+(l===-2?t:d)}return[Pe(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},Ie=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=Fe(t,n);if(this.el=e.createElement(l,r),A.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=A.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(Se)){let t=u[o++],n=i.getAttribute(e).split(x),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?ze:r[1]===`?`?Be:r[1]===`@`?Ve:M}),i.removeAttribute(e)}else e.startsWith(x)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(Me.test(i.tagName)){let e=i.textContent.split(x),t=e.length-1;if(t>0){i.textContent=be?be.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],C()),A.nextNode(),c.push({type:2,index:++a});i.append(e[t],C())}}}else if(i.nodeType===8){if(i.data===Ce)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(x,e+1))!==-1;)c.push({type:7,index:a}),e+=x.length-1}}a++}}static createElement(e,t){let n=S.createElement(`template`);return n.innerHTML=e,n}};function j(e,t,n=e,r){if(t===O)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=w(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=j(e,i._$AS(e,t.values),i,r)),t}var Le=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??S).importNode(t,!0);A.currentNode=r;let i=A.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new Re(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new He(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=A.nextNode(),a++)}return A.currentNode=S,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},Re=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=k,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=j(this,e,t),w(e)?e===k||e==null||e===``?(this._$AH!==k&&this._$AR(),this._$AH=k):e!==this._$AH&&e!==O&&this._(e):e._$litType$===void 0?e.nodeType===void 0?Ee(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==k&&w(this._$AH)?this._$AA.nextSibling.data=e:this.T(S.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=Ie.createElement(Pe(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new Le(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=Ne.get(e.strings);return t===void 0&&Ne.set(e.strings,t=new Ie(e)),t}k(t){Te(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(C()),this.O(C()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=ye(e).nextSibling;ye(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},M=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=k,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=k}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=j(this,e,t,0),a=!w(e)||e!==this._$AH&&e!==O,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=j(this,r[n+o],t,o),s===O&&(s=this._$AH[o]),a||=!w(s)||s!==this._$AH[o],s===k?e=k:e!==k&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===k?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},ze=class extends M{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===k?void 0:e}},Be=class extends M{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==k)}},Ve=class extends M{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=j(this,e,t,0)??k)===O)return;let n=this._$AH,r=e===k&&n!==k||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==k&&(n===k||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},He=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){j(this,e)}},Ue=ve.litHtmlPolyfillSupport;Ue?.(Ie,Re),(ve.litHtmlVersions??=[]).push(`3.3.3`);var We=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new Re(t.insertBefore(C(),e),e,void 0,n??{})}return i._$AI(e),i},Ge=globalThis,N=class extends b{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=We(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return O}};N._$litElement$=!0,N.finalized=!0,Ge.litElementHydrateSupport?.({LitElement:N});var Ke=Ge.litElementPolyfillSupport;Ke?.({LitElement:N}),(Ge.litElementVersions??=[]).push(`4.2.2`);var qe={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Je=e=>(...t)=>({_$litDirective$:e,values:t}),Ye=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},Xe=`important`,Ze=` !`+Xe,Qe=Je(class extends Ye{constructor(e){if(super(e),e.type!==qe.ATTRIBUTE||e.name!==`style`||e.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(e){return Object.keys(e).reduce((t,n)=>{let r=e[n];return r==null?t:t+`${n=n.includes(`-`)?n:n.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,`-$&`).toLowerCase()}:${r};`},``)}update(e,[t]){let{style:n}=e.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let e of this.ft)t[e]??(this.ft.delete(e),e.includes(`-`)?n.removeProperty(e):n[e]=null);for(let e in t){let r=t[e];if(r!=null){this.ft.add(e);let t=typeof r==`string`&&r.endsWith(Ze);e.includes(`-`)||t?n.setProperty(e,t?r.slice(0,-11):r,t?Xe:``):n[e]=r}}return O}});function $e(e){return`var(--${e}-color)`}var et=e=>Qe({"--tone":$e(e)});function tt(e,t,n=!1){return D`<span class="bubble ${n?`large`:``}" style=${et(t)} aria-hidden="true">
    <ha-icon .icon=${e}></ha-icon>
  </span>`}function P(e,t,n){return D`<span class="badge" style=${et(t)}>
    ${n?D`<ha-icon .icon=${n} aria-hidden="true"></ha-icon>`:k}<span>${e}</span>
  </span>`}function F(e,t){return D`<div class="empty"><ha-icon .icon=${e} aria-hidden="true"></ha-icon><span>${t}</span></div>`}function I(e,t){return D`<ha-alert alert-type=${e}>${t}</ha-alert>`}function L(e){return D`<div class="header">
    <ha-icon .icon=${e.icon} aria-hidden="true"></ha-icon>
    <h2 class="title">${e.title}${e.count?D` <span class="count">${e.count}</span>`:k}</h2>
    ${e.onDetails?D`<div class="actions">
            <ha-icon-button .label=${e.detailsLabel??``} @click=${e.onDetails}>
              <ha-icon icon="mdi:information-outline"></ha-icon>
            </ha-icon-button>
          </div>`:k}
  </div>`}function R(e){return D`<div class="row" role="listitem">
    <ha-md-list-item
      type=${e.onActivate?`button`:`text`}
      @click=${e.onActivate??k}
    >
      <span slot="start">${tt(e.icon,e.tone)}</span>
      <span slot="headline" class="headline">${e.headline}</span>
      ${e.badge?D`<span slot="supporting-text" class="row-badge">${e.badge}</span>`:k}
      ${e.supporting?D`<span slot="supporting-text" class="supporting">${e.supporting}</span>`:k}
      ${e.trailing?D`<span slot="end" class="trailing">${e.trailing}</span>`:k}
    </ha-md-list-item>
    ${e.link?D`<ha-icon-button
            class="link"
            .label=${e.linkLabel??``}
            .href=${e.link}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ha-icon icon="mdi:open-in-new"></ha-icon>
          </ha-icon-button>`:k}
  </div>`}function z(e,t){return D`<div class="list" role="list" aria-label=${t??k}>${e}</div>`}function nt(e,t,n,r){return D`<ha-button
    class="more"
    appearance="plain"
    size="s"
    aria-expanded=${t?`true`:`false`}
    @click=${r}
    >${t?f(e,`action.show_less`):f(e,`action.show_all`,{count:n})}</ha-button
  >`}var rt=new WeakMap;function it(e){let t=e.entities,n=rt.get(t);if(n)return n;let r=new Map,i=new Map;for(let t of Object.values(e.entities??{}))if(t.platform===`ausnz_disaster_watch`&&t.device_id){if(t.translation_key){let e=r.get(t.device_id);e||r.set(t.device_id,e=new Map),e.set(t.translation_key,t.entity_id)}if(t.entity_id.startsWith(`camera.`)){let e=i.get(t.device_id)??[];e.push(t.entity_id),i.set(t.device_id,e)}}let a=new Set([...r.keys(),...i.keys()]),o=Object.keys(e.devices??{}).filter(e=>a.has(e));for(let e of a)o.includes(e)||o.push(e);let s={devices:o,byKey:r,cameras:i};return rt.set(t,s),s}function B(e){return it(e).devices}function at(e,t){return t||B(e)[0]}function ot(e,t){return!!t&&B(e).includes(t)}function st(t,n){if(!n)return;let r=t.devices?.[n];if(!r)return;let i=r.identifiers?.find(([t])=>t===e);return i?i[1]:r.config_entries?.[0]}function ct(e,t){if(!t)return;let n=e.devices?.[t];return n?.name_by_user||n?.name||void 0}function lt(e,t,n){if(t)return it(e).byKey.get(t)?.get(n)}function V(e,t,n){let r=lt(e,t,n);return r?e.states[r]:void 0}function ut(e,t){return t?[...it(e).cameras.get(t)??[]].sort((t,n)=>{let r=String(e.states[t]?.attributes.friendly_name??t),i=String(e.states[n]?.attributes.friendly_name??n);return r.localeCompare(i)}):[]}var dt=new WeakMap;function ft(e,t){if(!t)return[];let n=dt.get(e.states);n||dt.set(e.states,n=new Map);let r=n.get(t);if(r)return r;let i=Object.values(e.states).filter(e=>e.entity_id.startsWith(`geo_location.`)&&e.attributes.integration===`ausnz_disaster_watch`&&e.attributes.entry_id===t).sort((e,t)=>(mt(e)??1/0)-(mt(t)??1/0));return n.set(t,i),i}function pt(e){let t=e.attributes.title??e.attributes.friendly_name;return typeof t==`string`&&t?t:e.entity_id}function mt(e){let t=Number.parseFloat(e.state);if(Number.isFinite(t))return t;let n=e.attributes.distance_km;return typeof n==`number`&&Number.isFinite(n)?n:void 0}var ht=[`ha-card`,`ha-icon`,`ha-icon-button`,`ha-button`,`ha-alert`,`ha-assist-chip`,`ha-filter-chip`,`ha-chip-set`,`ha-md-list-item`,`ha-tooltip`],gt;function _t(e=5e3){return gt??=(async()=>{try{await window.loadCardHelpers?.()}catch{}await Promise.race([Promise.all(ht.map(e=>customElements.whenDefined(e))),new Promise(t=>setTimeout(t,e))])})(),gt}var vt=_`
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
  .header .title {
    flex: 1;
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
  .row ha-md-list-item {
    flex: 1;
    min-width: 0;
    --md-list-item-leading-space: var(--ha-space-4);
    --md-list-item-trailing-space: var(--ha-space-4);
    --md-list-item-top-space: var(--ha-space-2);
    --md-list-item-bottom-space: var(--ha-space-2);
    --md-list-item-label-text-size: var(--ha-font-size-m);
    --md-list-item-supporting-text-size: var(--ha-font-size-s);
    --md-list-item-trailing-supporting-text-size: var(--ha-font-size-s);
    --ha-md-list-item-gap: var(--ha-space-3);
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
`;function yt(e,t,n){e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0}))}function bt(e,t){t&&yt(e,`hass-more-info`,{entityId:t})}var H=class extends N{static properties={hass:{attribute:!1},embedded:{type:Boolean,reflect:!0},_config:{state:!0}};static styles=[vt];constructor(){super(),this.embedded=!1}entityKeys(){return[]}usesIncidents=!1;extraEntityIds(e){return[]}static validateConfig(e){if(!e||typeof e!=`object`)throw Error(`Invalid configuration`);if(e.device!==void 0&&typeof e.device!=`string`)throw Error(`'device' must be a device ID`);if(e.title!==void 0&&typeof e.title!=`string`)throw Error(`'title' must be text`)}setConfig(e){this.constructor.validateConfig(e),this._config={...e}}get config(){return this._config}get deviceId(){return this.hass?at(this.hass,this._config?.device):void 0}get entryId(){return this.hass?st(this.hass,this.deviceId):void 0}entityId(e){return this.hass?lt(this.hass,this.deviceId,e):void 0}cardTitle(){return this._config?.title||f(this.hass,this.titleKey)}moreInfo(e){bt(this,e)}trackedEntityIds(e){let t=at(e,this._config?.device),n=[];for(let r of this.entityKeys()){let i=lt(e,t,r);i&&n.push(i)}if(this.usesIncidents)for(let r of ft(e,st(e,t)))n.push(r.entity_id);return n.push(...this.extraEntityIds(e)),n}shouldUpdate(e){if(!e.has(`hass`)||e.size>1)return!0;let t=e.get(`hass`),n=this.hass;if(!t||!n||t.entities!==n.entities||t.devices!==n.devices||t.locale!==n.locale||t.themes?.darkMode!==n.themes?.darkMode)return!0;let r=new Set([...this.trackedEntityIds(t),...this.trackedEntityIds(n)]);for(let e of r)if(t.states[e]!==n.states[e])return!0;return!1}connectedCallback(){super.connectedCallback(),_t()}getCardSize(){return 3}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}renderSetupState(e){if(B(e).length===0)return D`<div class="content">${I(`info`,f(e,`state.not_set_up`))}</div>`;if(this._config?.device&&!ot(e,this._config.device))return D`<div class="content">${I(`warning`,f(e,`state.device_missing`))}</div>`}render(){if(!this._config||!this.hass)return k;let e=this.renderSetupState(this.hass)??this.renderBody(this.hass,this._config);return this.embedded?D`<section class="embedded" aria-label=${this.cardTitle()}>${e}</section>`:D`<ha-card>${e}</ha-card>`}};function U(e){let t=e?B(e)[0]:void 0;return t?{device:t}:{}}function W(){return[{name:`device`,selector:{device:{filter:{integration:e}}}},{name:`title`,selector:{text:{}}}]}var xt={device:`editor.device`,title:`editor.title`,max_items:`editor.max_items`,show_planned_burns:`editor.show_planned_burns`,categories:`editor.categories`,refresh_interval:`editor.refresh_interval`,zoom:`editor.zoom`,radar:`editor.radar`,radar_opacity:`editor.radar_opacity`,satellite_layer:`editor.satellite_layer`,show_cyclone_tracks:`editor.show_cyclone_tracks`,cards:`editor.cards`},St={device:`editor.device_helper`,title:`editor.title_helper`,max_items:`editor.max_items_helper`,show_planned_burns:`editor.show_planned_burns_helper`,categories:`editor.categories_helper`,refresh_interval:`editor.refresh_interval_helper`,zoom:`editor.zoom_helper`,radar:`editor.radar_helper`,satellite_layer:`editor.satellite_layer_helper`,show_cyclone_tracks:`editor.show_cyclone_tracks_helper`,cards:`editor.cards_helper`},G=e=>{let t=xt[e.name];return t?f(void 0,t):void 0},K=e=>{let t=St[e.name];return t?f(void 0,t):void 0};function q(e,t,n=1,r=1e3){let i=e[t];if(i!=null&&(typeof i!=`number`||!Number.isInteger(i)||i<n||i>r))throw Error(`'${t}' must be a whole number from ${n} to ${r}`)}function Ct(e,t,n,r){let i=e[t];if(i!=null&&(typeof i!=`number`||!Number.isFinite(i)||i<n||i>r))throw Error(`'${t}' must be a number from ${n} to ${r}`)}function wt(e,t){let n=e[t];if(n!==void 0&&typeof n!=`boolean`)throw Error(`'${t}' must be true or false`)}function Tt(e,t,n){let r=e[t];if(r!=null&&(typeof r!=`string`||!n.includes(r)))throw Error(`'${t}' must be one of: ${n.join(`, `)}`)}function Et(e,t,n){let r=e[t];if(r!=null&&(!Array.isArray(r)||r.some(e=>typeof e!=`string`||!n.includes(e))))throw Error(`'${t}' must be a list of: ${n.join(`, `)}`)}var Dt={status:`card.status.name`,incidents:`card.incidents.name`,warnings:`card.warnings.name`,fire_danger:`card.fire_danger.name`,outages:`card.outages.name`,roads:`card.roads.name`,conditions:`card.conditions.name`,relief:`card.relief.name`,cameras:`card.cameras.name`,map:`card.map.name`},Ot=class e extends N{static properties={_config:{state:!0}};static styles=[vt,_`
      .title {
        margin: 0;
        padding: var(--ha-space-4) var(--ha-space-4) 0;
        font-family: var(--ha-font-family-heading);
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-medium);
        line-height: var(--ha-line-height-condensed);
      }
    `];_children=new Map;_hass;set hass(e){let t=e=>!!e&&B(e).length>0;if((t(e)!==t(this._hass)||!this._hass)&&this.requestUpdate(),this._hass=e,e)for(let t of this._children.values())t.hass=e}get hass(){return this._hass}static validateConfig(e){H.validateConfig(e),Et(e,`cards`,o)}static getConfigForm(){return{schema:[...W(),{name:`cards`,selector:{select:{multiple:!0,reorder:!0,mode:`list`,options:o.map(e=>({value:e,label:f(void 0,Dt[e])}))}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}setConfig(t){e.validateConfig(t),this._config={...t}}sections(){return this._config?.cards?.length?this._config.cards:a}connectedCallback(){super.connectedCallback(),_t()}getCardSize(){return this.sections().length*3}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}willUpdate(e){if(this._config){if(e.has(`_config`)){let e=new Set(this.sections());for(let t of[...this._children.keys()])e.has(t)||this._children.delete(t);for(let t of e){let e=this._children.get(t);e||(e=document.createElement(r[t]),e.embedded=!0,this._children.set(t,e)),e.setConfig({type:`custom:${r[t]}`,device:this._config.device})}}if(this._hass)for(let e of this._children.values())e.hass=this._hass}}render(){if(!this._config)return k;let e=this.sections().map(e=>this._children.get(e)).filter(e=>!!e);return this._hass&&B(this._hass).length===0?D`<ha-card><div class="content">${I(`info`,f(this._hass,`state.not_set_up`))}</div></ha-card>`:D`<ha-card>
      ${this._config.title?D`<h2 class="title">${this._config.title}</h2>`:k}
      ${e.map((e,t)=>D`${t?D`<hr class="divider" />`:k}${e}`)}
    </ha-card>`}},kt=new Set([`unavailable`,`unknown`]);function J(e){return!e||kt.has(e.state)}function At(e){return e.locale?.language||e.language||`en`}function jt(e){return e.locale?.time_zone===`server`?e.config?.time_zone:void 0}function Mt(e,t){if(e.formatEntityState)return e.formatEntityState(t);let n=t.attributes.unit_of_measurement;return n?`${t.state} ${n}`:t.state}function Nt(e,t,n,r){let i=r===void 0?t.attributes[n]:r;return e.formatEntityAttributeValue?e.formatEntityAttributeValue(t,n,i):typeof i==`number`?Y(e,i):String(i??``)}function Y(e,t,n){try{return new Intl.NumberFormat(At(e),n).format(t)}catch{return String(t)}}function Pt(e,t){if(t!=null&&Number.isFinite(t))return`${Y(e,t,{maximumFractionDigits:+(t<10)})} km`}function Ft(e){if(typeof e!=`string`&&typeof e!=`number`)return;let t=typeof e==`string`?/^\/Date\((-?\d+)(?:[+-]\d{4})?\)\/$/.exec(e.trim()):null;if(t)return new Date(Number(t[1]));let n=new Date(e);return Number.isNaN(n.getTime())?void 0:n}var It=[[`year`,31536e3],[`month`,2592e3],[`week`,604800],[`day`,86400],[`hour`,3600],[`minute`,60],[`second`,1]];function X(e,t,n=Date.now()){let r=Ft(t);if(!r)return;let i=Math.round((r.getTime()-n)/1e3),a=new Intl.RelativeTimeFormat(At(e),{numeric:`auto`});for(let[e,t]of It)if(Math.abs(i)>=t||e===`second`)return a.format(Math.round(i/t),e)}function Lt(e,t,n={dateStyle:`medium`,timeStyle:`short`}){let r=Ft(t);if(r)try{return new Intl.DateTimeFormat(At(e),{...n,timeZone:jt(e)}).format(r)}catch{return r.toISOString()}}function Rt(e){if(typeof e!=`string`||!e.trim())return;let t;try{t=new URL(e.trim())}catch{return}return t.protocol===`http:`||t.protocol===`https:`?t.href:void 0}function Z(e){if(typeof e==`number`)return Number.isFinite(e)?e:void 0;if(typeof e==`string`&&e.trim()!==``){let t=Number(e);return Number.isFinite(t)?t:void 0}}function Q(e){return typeof e==`string`&&e.trim()?e.trim():void 0}function $(e){return Array.isArray(e)?e.filter(e=>e&&typeof e==`object`):[]}var zt=e=>`/api/camera_proxy/${e}`,Bt=10,Vt=class extends H{static properties={...H.properties,_tick:{state:!0},_failed:{state:!0},_signed:{state:!0}};static styles=[...H.styles,_`
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
    `];_signing=new Set;titleKey=`cameras.title`;_timer;_observer;_visible=!1;_onVisibility=()=>this.updateTimer();constructor(){super(),this._tick=0,this._failed=new Set,this._signed={}}extraEntityIds(e){return ut(e,at(e,this.config?.device))}static validateConfig(e){super.validateConfig(e),q(e,`refresh_interval`,Bt,3600)}static getConfigForm(){return{schema:[...W(),{name:`refresh_interval`,selector:{number:{min:Bt,max:3600,step:5,mode:`box`,unit_of_measurement:`s`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 4}connectedCallback(){super.connectedCallback(),document.addEventListener(`visibilitychange`,this._onVisibility),`IntersectionObserver`in window?(this._observer=new IntersectionObserver(e=>{this._visible=e.some(e=>e.isIntersecting),this.updateTimer()}),this._observer.observe(this)):(this._visible=!0,this.updateTimer())}disconnectedCallback(){super.disconnectedCallback(),document.removeEventListener(`visibilitychange`,this._onVisibility),this._observer?.disconnect(),this._observer=void 0,this._visible=!1,this.updateTimer()}updated(e){super.updated(e),this.signMissing(),e.has(`_config`)&&this._timer&&(clearInterval(this._timer),this._timer=void 0,this.updateTimer())}updateTimer(){let e=this._visible&&document.visibilityState===`visible`&&this.isConnected;if(e&&!this._timer){let e=this._config?.refresh_interval??60;this._timer=setInterval(()=>{this._failed=new Set,this._tick+=1},e*1e3)}else!e&&this._timer&&(clearInterval(this._timer),this._timer=void 0)}signMissing(){let e=this.hass;if(e)for(let t of ut(e,this.deviceId)){let n=e.states[t];if(!n||J(n)||Q(n.attributes.entity_picture))continue;let r=`${t}@${this._tick}`;this._signed[r]||this._signing.has(r)||(this._signing.add(r),e.connection.sendMessagePromise({type:`auth/sign_path`,path:zt(t),expires:300}).then(e=>{e?.path&&(this._signed={...this.prune(),[r]:e.path})}).catch(()=>void 0).finally(()=>this._signing.delete(r)))}}prune(){return Object.fromEntries(Object.entries(this._signed).filter(([e])=>e.endsWith(`@${this._tick}`)))}imageUrl(e){return this._tick?`${e}${e.includes(`?`)?`&`:`?`}t=${this._tick}`:e}renderBody(e,t){let n=ut(e,this.deviceId);return D`${L({title:this.cardTitle(),icon:`mdi:cctv`,count:n.length?String(n.length):void 0})}
      <div class="content">
        ${n.length?D`<div class="grid" role="list">
                ${n.map(t=>{let n=e.states[t],r=Q(e.entities[t]?.name)??Q(n?.attributes.friendly_name)??t,i=J(n)?void 0:Q(n?.attributes.entity_picture),a=i?this.imageUrl(i):this._signed[`${t}@${this._tick}`],o=a&&!this._failed.has(a);return D`<div role="listitem">
                    <button class="plain camera" aria-label=${`${r}. ${f(e,`action.details`)}`} @click=${()=>this.moreInfo(t)}>
                      <span class="frame">
                        ${o?D`<img
                                src=${a}
                                alt=${r}
                                loading="lazy"
                                @error=${()=>this._failed=new Set([...this._failed,a])}
                              />`:D`<span class="placeholder">
                                <ha-icon icon="mdi:image-off-outline" aria-hidden="true"></ha-icon>
                                <span>${f(e,`cameras.no_image`)}</span>
                              </span>`}
                      </span>
                      <span class="name">${r}</span>
                    </button>
                  </div>`})}
              </div>`:F(`mdi:cctv-off`,f(e,`cameras.empty`))}
      </div>`}},Ht=[`moderate`,`high`,`extreme`,`catastrophic`],Ut={moderate:`green`,high:`yellow`,extreme:`orange`,catastrophic:`red`,no_rating:`grey`},Wt={moderate:`mdi:fire`,high:`mdi:fire`,extreme:`mdi:fire-alert`,catastrophic:`mdi:fire-alert`,no_rating:`mdi:fire-off`};function Gt(e){if(typeof e!=`string`)return`no_rating`;let t=e.trim().toLowerCase();return t.includes(`catastrophic`)?`catastrophic`:t.includes(`extreme`)?`extreme`:t.includes(`high`)?`high`:t.includes(`moderate`)?`moderate`:`no_rating`}function Kt(e){return Ut[e]}var qt={good:`green`,fair:`yellow`,poor:`orange`,very_poor:`red`,extremely_poor:`purple`,unknown:`grey`};function Jt(e){if(typeof e!=`string`)return`unknown`;let t=e.trim().toLowerCase();return t.includes(`extremely`)||t.includes(`hazardous`)?`extremely_poor`:t.includes(`very poor`)||t.includes(`very_poor`)?`very_poor`:t.includes(`poor`)?`poor`:t.includes(`fair`)||t.includes(`moderate`)?`fair`:t.includes(`good`)||t.includes(`very good`)?`good`:`unknown`}function Yt(e){return qt[e]}function Xt(e){if(typeof e!=`string`)return`grey`;let t=e.toLowerCase();return t.includes(`closed`)||t.includes(`closure`)?`red`:t.includes(`flood`)?`blue`:t.includes(`hazard`)||t.includes(`caution`)||t.includes(`restrict`)||t.includes(`lane`)?`amber`:t.includes(`open`)?`green`:`grey`}function Zt(e){let t=Xt(e);return t===`red`?`mdi:road-variant`:t===`blue`?`mdi:waves`:t===`amber`?`mdi:traffic-cone`:`mdi:road`}var Qt=[`N`,`NNE`,`NE`,`ENE`,`E`,`ESE`,`SE`,`SSE`,`S`,`SSW`,`SW`,`WSW`,`W`,`WNW`,`NW`,`NNW`];function $t(e){return Qt[Math.round((e%360+360)%360/22.5)%16]}var en=[{attr:`pm2_5`,label:`PM2.5`},{attr:`pm10`,label:`PM10`},{attr:`no2`,label:`NO₂`},{attr:`o3`,label:`O₃`}],tn=class extends H{static styles=[...H.styles,_`
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
    `];titleKey=`conditions.title`;entityKeys(){return[n.primaryWeatherObservation,n.airQualityRating]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 4}metric(e,t){return t===void 0||t===``?k:D`<div class="metric"><dt>${e}</dt><dd>${t}</dd></div>`}renderWeather(e,t){if(!t||J(t))return F(`mdi:weather-cloudy-alert`,f(e,`conditions.no_weather`));let n=t.attributes,r=(r,i)=>{let a=Z(n[r]);return a===void 0?void 0:`${Nt(e,t,r,a)} ${i}`},i=Z(n.wind_direction_deg),a=r(`wind_speed_avg_kph`,`km/h`),o=Z($(n.stations)[0]?.rain_since_9am),s=Q(n.station_name),c=a===void 0?void 0:D`${i===void 0?k:D`<ha-icon
                    icon="mdi:navigation"
                    style=${Qe({transform:`rotate(${i+180}deg)`})}
                    aria-hidden="true"
                  ></ha-icon>`}<span>${a}${i===void 0?``:` ${$t(i)}`}</span>${i===void 0?k:D`<span class="sr-only">${f(e,`conditions.wind_from`,{direction:$t(i)})}</span>`}`;return D`<button
        class="plain temperature"
        aria-label=${`${f(e,`conditions.temperature`)} ${Mt(e,t)}. ${f(e,`action.details`)}`}
        @click=${()=>this.moreInfo(t.entity_id)}
      >
        <span class="value">${Mt(e,t)}</span>
        ${s?D`<span class="secondary">${f(e,`conditions.station`,{name:s})}</span>`:k}
      </button>
      <dl class="metrics">
        ${this.metric(f(e,`conditions.feels_like`),r(`apparent_temperature`,`°C`))}
        ${this.metric(f(e,`conditions.humidity`),r(`relative_humidity`,`%`))}
        ${this.metric(f(e,`conditions.wind`),c)}
        ${this.metric(f(e,`conditions.gust`),r(`wind_speed_max_kph`,`km/h`))}
        ${this.metric(f(e,`conditions.pressure`),r(`pressure_hpa`,`hPa`))}
        ${this.metric(f(e,`conditions.rain`),o===void 0?void 0:`${Nt(e,t,`rain_since_9am`,o)} mm`)}
      </dl>`}renderAirQuality(e,t){if(!t||J(t))return F(`mdi:air-filter`,f(e,`conditions.no_air_quality`));let n=Q(t.attributes.station_name);return D`<dl class="metrics">
        ${en.map(n=>this.metric(n.label,Q(t.attributes[n.attr])??(Z(t.attributes[n.attr])===void 0?void 0:Nt(e,t,n.attr))))}
      </dl>
      ${n?D`<span class="secondary">${f(e,`conditions.station`,{name:n})}</span>`:k}`}renderBody(e,t){let r=V(e,this.deviceId,n.primaryWeatherObservation),i=V(e,this.deviceId,n.airQualityRating),a=Jt(J(i)?void 0:i?.state),o=J(i)?void 0:a===`unknown`?Q(i?.state):f(e,`conditions.aq.${a}`);return D`${L({title:this.cardTitle(),icon:`mdi:weather-partly-cloudy`})}
      <div class="content">
        <section class="group" aria-label=${f(e,`conditions.weather`)}>${this.renderWeather(e,r)}</section>
        <hr class="divider" />
        <section class="group" aria-label=${f(e,`conditions.air_quality`)}>
          <div class="group-head">
            <h3 class="group-title">${f(e,`conditions.air_quality`)}</h3>
            ${o?D`<button class="plain" aria-label=${`${f(e,`conditions.air_quality`)}: ${o}. ${f(e,`action.details`)}`} @click=${()=>this.moreInfo(i?.entity_id)}>
                    ${P(o,Yt(a),`mdi:air-filter`)}
                  </button>`:k}
          </div>
          ${this.renderAirQuality(e,i)}
        </section>
      </div>`}},nn=class extends H{static styles=[...H.styles,_`
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
    `];titleKey=`fire.title`;entityKeys(){return[n.fireDangerRating]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getGridOptions(){return{columns:6,rows:`auto`,min_columns:6}}renderBody(e,t){let r=V(e,this.deviceId,n.fireDangerRating),i=L({title:this.cardTitle(),icon:`mdi:fire`,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(!r||r.state===`unavailable`)return D`${i}<div class="content">
          ${I(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let a=Gt(J(r)?void 0:r.state),o=Kt(a),s=f(e,`fire.rating.${a}`),c=Q(r.attributes.district_name),l=Q(r.attributes.day),u=r.attributes.total_fire_ban===!0;return D`${i}
      <div class="content">
        <div class="rating">
          ${tt(Wt[a],o,!0)}
          <div class="rating-text">
            <span class="rating-label">${s}</span>
            ${c||l?D`<span class="secondary"
                    >${[c?f(e,`fire.district`,{district:c}):void 0,l?f(e,`fire.forecast_for`,{day:l}):void 0].filter(Boolean).join(` · `)}</span
                  >`:k}
          </div>
        </div>
        <ol class="scale" aria-label=${f(e,`fire.scale`)}>
          ${Ht.map(t=>{let n=t===a,r=f(e,`fire.rating.${t}`);return D`<li
              class="segment ${n?`active`:``}"
              style=${Qe({"--tone":$e(Kt(t))})}
              aria-current=${n?`true`:k}
            >
              <span class="bar" aria-hidden="true"></span>
              <span class="name">${r}</span>
              ${n?D`<span class="sr-only">${f(e,`fire.current`)}</span>`:k}
            </li>`})}
        </ol>
        <div class="badges">
          ${u?P(f(e,`fire.total_fire_ban`),`red`,`mdi:fire-off`):P(f(e,`fire.no_total_fire_ban`),`grey`,`mdi:check`)}
        </div>
      </div>`}},rn={emergency:{level:`emergency`,tone:`red`,icon:`mdi:alert-octagon`,rank:4},watch_and_act:{level:`watch_and_act`,tone:`orange`,icon:`mdi:alert`,rank:3},advice:{level:`advice`,tone:`amber`,icon:`mdi:information`,rank:2},information:{level:`information`,tone:`blue`,icon:`mdi:information-outline`,rank:1},unknown:{level:`unknown`,tone:`grey`,icon:`mdi:help-circle-outline`,rank:0}};function an(e){if(typeof e!=`string`)return`unknown`;let t=e.trim().toLowerCase();return t.includes(`emergency`)?`emergency`:t.includes(`watch and act`)||t.includes(`watch & act`)?`watch_and_act`:t.includes(`advice`)?`advice`:t.includes(`info`)||t.includes(`routine`)||t.includes(`notification`)?`information`:`unknown`}function on(e){return rn[an(e)]}function sn(e,t){return e===void 0||e===`unavailable`||e===`unknown`?`unavailable`:e.trim().toLowerCase()===`all clear`?t===void 0||t>0?`unknown`:`all_clear`:an(e)}function cn(e){return e===`all_clear`?{level:`unknown`,tone:`green`,icon:`mdi:shield-check`,rank:0}:e===`unavailable`?{level:`unknown`,tone:`grey`,icon:`mdi:cloud-off-outline`,rank:-1}:rn[e]}var ln=[`fire`,`flood_storm`,`geological`,`roads`,`other`],un={Bushfire:{category:`fire`,icon:`mdi:fire`},"Grass Fire":{category:`fire`,icon:`mdi:grass`},"Structure Fire":{category:`fire`,icon:`mdi:fire-alert`},Flood:{category:`flood_storm`,icon:`mdi:water-alert`},"Severe Storm":{category:`flood_storm`,icon:`mdi:weather-lightning`},"Tropical Cyclone":{category:`flood_storm`,icon:`mdi:weather-hurricane`},Earthquake:{category:`geological`,icon:`mdi:pulse`},Volcano:{category:`geological`,icon:`mdi:volcano`},Tsunami:{category:`geological`,icon:`mdi:tsunami`},"Road Hazard / Crash":{category:`roads`,icon:`mdi:car-emergency`},"Hazmat Incident":{category:`other`,icon:`mdi:biohazard`},Other:{category:`other`,icon:`mdi:alert-decagram`}},dn={fire:`mdi:fire`,flood_storm:`mdi:weather-pouring`,geological:`mdi:earth`,roads:`mdi:car-emergency`,other:`mdi:alert-decagram`};function fn(e){return typeof e==`string`&&un[e]?.category||`other`}function pn(e){return typeof e==`string`&&un[e]?.icon||`mdi:alert-decagram`}var mn=10,hn={emergency:`status.level.emergency`,watch_and_act:`status.level.watch_and_act`,advice:`status.level.advice`,information:`status.level.information`,unknown:`status.level.unknown`},gn=class extends H{static properties={...H.properties,_category:{state:!0},_showBurns:{state:!0},_expanded:{state:!0}};titleKey=`incidents.title`;usesIncidents=!0;constructor(){super(),this._category=`all`,this._showBurns=void 0,this._expanded=!1}static validateConfig(e){super.validateConfig(e);let t=e;q(t,`max_items`,1,100),wt(t,`show_planned_burns`),Et(t,`categories`,ln)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}},{name:`show_planned_burns`,selector:{boolean:{}}},{name:`categories`,selector:{select:{multiple:!0,mode:`list`,options:ln.map(e=>({value:e,label:f(void 0,`incidents.category.${e}`)}))}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 2+Math.min(this._config?.max_items??mn,6)}get showBurns(){return this._showBurns??this._config?.show_planned_burns??!1}categories(){let e=this._config?.categories;return e?.length?e:ln}renderIncident(e,t){let n=t.attributes,r=on(n.warning_level),i=pt(t),a=X(e,n.updated_at),o=[Q(n.location_name),Pt(e,mt(t)),a?f(e,`incidents.updated`,{time:a}):void 0].filter(Boolean).join(` · `);return R({icon:Q(n.icon)??pn(n.hazard_type),tone:r.tone,headline:i,supporting:D`${n.is_hazard_reduction?D`${f(e,`incidents.planned_burn`)} · `:k}${o}`,badge:P(f(e,hn[r.level]),r.tone,r.icon),onActivate:()=>this.moreInfo(t.entity_id),link:Rt(n.web_url),linkLabel:`${f(e,`action.open_link`)}: ${i}`})}renderBody(e,t){let n=this.categories(),r=ft(e,this.entryId).filter(e=>n.includes(fn(e.attributes.hazard_type))),i=r.some(e=>e.attributes.is_hazard_reduction===!0),a=this.showBurns?r:r.filter(e=>e.attributes.is_hazard_reduction!==!0),o=new Map;for(let e of a){let t=fn(e.attributes.hazard_type);o.set(t,(o.get(t)??0)+1)}let s=this._category!==`all`&&n.includes(this._category)?this._category:`all`,c=s===`all`?a:a.filter(e=>fn(e.attributes.hazard_type)===s),l=t.max_items??mn,u=this._expanded?c:c.slice(0,l),d=(t,n)=>D`<ha-filter-chip
      .selected=${s===t}
      .label=${`${f(e,`incidents.category.${t}`)} ${n}`}
      @click=${e=>{e.preventDefault(),this._category=t,this._expanded=!1}}
    >
      ${t===`all`?k:D`<ha-icon slot="icon" .icon=${dn[t]}></ha-icon>`}
    </ha-filter-chip>`;return D`${L({title:this.cardTitle(),icon:`mdi:alert-decagram`,count:String(a.length)})}
      <div class="content">
        ${r.length?D`<ha-chip-set aria-label=${f(e,`incidents.filters`)}>
                ${d(`all`,a.length)}
                ${n.length>1?n.map(e=>d(e,o.get(e)??0)):k}
                ${i?D`<ha-filter-chip
                        .selected=${this.showBurns}
                        .label=${f(e,`incidents.planned_burns`)}
                        @click=${e=>{e.preventDefault(),this._showBurns=!this.showBurns}}
                      >
                        <ha-icon slot="icon" icon="mdi:fire-circle"></ha-icon>
                      </ha-filter-chip>`:k}
              </ha-chip-set>`:k}
        ${u.length?z(u.map(t=>this.renderIncident(e,t)),this.cardTitle()):F(`mdi:shield-check-outline`,f(e,r.length?`incidents.empty_filtered`:`incidents.empty`))}
        ${c.length>l?nt(e,this._expanded,c.length,()=>this._expanded=!this._expanded):k}
      </div>`}},_n=`<a href="https://www.gdacs.org/About/termofuse.aspx" target="_blank" rel="noopener noreferrer">GDACS</a> (EC JRC / UN OCHA)`,vn=18e5,yn=500;function bn(e){if(typeof e!=`string`)return!1;let t;try{t=new URL(e)}catch{return!1}return t.origin===`https://www.gdacs.org`&&t.username===``&&t.password===``&&t.pathname===`/gdacsapi/api/polygons/getgeometry`&&t.searchParams.get(`eventtype`)===`TC`&&/^\d+$/.test(t.searchParams.get(`eventid`)??``)&&/^\d+$/.test(t.searchParams.get(`episodeid`)??``)}function xn(e){if(!Array.isArray(e))return[];let t=[],n=new Set;for(let r of e){if(!r||typeof r!=`object`)continue;let{geometry_url:e,title:i}=r;if(bn(e)&&!n.has(e)&&(n.add(e),t.push({url:e,name:typeof i==`string`?i:``}),t.length>=5))break}return t}function Sn(e,t){if(typeof e==`string`){if(e===`Poly_Green`)return`buffer-green`;if(e===`Poly_Orange`)return`buffer-orange`;if(e===`Poly_Red`)return`buffer-red`;if(e===`Poly_Cones`)return`cone`;if(e.startsWith(`Line_`))return t===!0?`track-forecast`:`track`}}var Cn={"buffer-green":[`Polygon`,`MultiPolygon`],"buffer-orange":[`Polygon`,`MultiPolygon`],"buffer-red":[`Polygon`,`MultiPolygon`],cone:[`Polygon`,`MultiPolygon`],track:[`LineString`,`MultiLineString`],"track-forecast":[`LineString`,`MultiLineString`]};function wn(e){if(!Array.isArray(e))return e;if(typeof e[0]==`number`){let[t,...n]=e;return[t<-90?t+360:t,...n]}return e.map(wn)}var Tn=[`cone`,`buffer-green`,`buffer-orange`,`buffer-red`,`track`,`track-forecast`];function En(e,t=``){let n=e;if(n?.type!==`FeatureCollection`||!Array.isArray(n.features))throw Error(`GDACS: not GeoJSON`);let r=[],i=t;for(let e of n.features.slice(0,yn)){let t=e?.properties??{},n=e?.geometry,a=Sn(t.Class,t.forecast);a&&typeof n?.type==`string`&&Array.isArray(n.coordinates)&&Cn[a].includes(n.type)&&(!i&&typeof t.name==`string`&&(i=t.name),r.push({part:a,geometry:{type:n.type,coordinates:wn(n.coordinates)}}))}return r.sort((e,t)=>Tn.indexOf(e.part)-Tn.indexOf(t.part)),{name:i,shapes:r}}var Dn=new Map,On=new Map;async function kn(e,t=Date.now(),n=fetch){if(!bn(e.url))throw Error(`GDACS: URL not allowed`);let r=Dn.get(e.url);if(r&&t-r.at<vn)return r.data;let i=On.get(e.url);return i||(i=(async()=>{try{let r=await n(e.url,{credentials:`omit`,referrerPolicy:`no-referrer`});if(!r.ok)throw Error(`GDACS: HTTP ${r.status}`);let i=En(await r.json(),e.name);return Dn.set(e.url,{at:t,data:i}),i}finally{On.delete(e.url)}})(),On.set(e.url,i)),i}var An=`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best`,jn=[`none`,`himawari_visible`,`himawari_ir`,`viirs_truecolor`],Mn=`<a href="https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance" target="_blank" rel="noopener noreferrer">NASA GIBS</a>`,Nn=`Imagery: ${Mn} / Himawari-9 (JMA)`,Pn=`Imagery: ${Mn} / VIIRS NOAA-21`,Fn={himawari_visible:{id:`himawari_visible`,layer:`Himawari_AHI_Band3_Red_Visible_1km`,maxNativeZoom:7,format:`png`,cadence:`10min`,opacity:.6,attribution:Nn},himawari_ir:{id:`himawari_ir`,layer:`Himawari_AHI_Band13_Clean_Infrared`,maxNativeZoom:6,format:`png`,cadence:`10min`,opacity:.6,attribution:Nn},viirs_truecolor:{id:`viirs_truecolor`,layer:`VIIRS_NOAA21_CorrectedReflectance_TrueColor`,maxNativeZoom:9,format:`jpg`,cadence:`daily`,opacity:.9,attribution:Pn}},In=108e5,Ln=6e5,Rn=864e5,zn=2e3;function Bn(e){return`GoogleMapsCompatible_Level${e.maxNativeZoom}`}function Vn(e){return new Date(Math.floor(e/6e4)*6e4).toISOString().replace(/:\d{2}\.\d{3}Z$/,`:00Z`)}function Hn(e){return new Date(e).toISOString().slice(0,10)}function Un(e,t,n){return`${An}/1.0.0/${e.layer}/default/${Bn(e)}/all/${Vn(t)}--${Vn(n)}.xml`}function Wn(e,t){return`${An}/${e.layer}/default/${t}/${Bn(e)}/{z}/{y}/{x}.${e.format}`}var Gn=/^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$/;function Kn(e){let t=Gn.exec(e.trim());if(!t||e.trim()===`P`||e.trim()===`PT`)return;let[,n,r,i]=t,a=(Number(n??0)*24*60+Number(r??0)*60+Number(i??0))*6e4;return a>0?a:void 0}function qn(e){let t=[...e.matchAll(/<Domain>([^<]*)<\/Domain>/g)].map(e=>e[1]),n=new Set;for(let e of t)for(let t of e.split(`,`)){let[e,r,i]=t.trim().split(`/`),a=Date.parse(e??``);if(Number.isNaN(a))continue;let o=r?Date.parse(r):a,s=i?Kn(i):void 0;if(!(Number.isNaN(o)||o<a)){if(!s)n.add(a);else for(let e=a;e<=o&&n.size<zn;e+=s)n.add(e)}}return[...n].sort((e,t)=>e-t)}var Jn=new Map,Yn=new Map;async function Xn(e,t=Date.now(),n=fetch,r=7){let i=Jn.get(e.id);if(i&&t-i.at<Ln)return i.times;let a=Yn.get(e.id);return a||(a=(async()=>{try{let i=await n(Un(e,t-In,t),{credentials:`omit`,referrerPolicy:`no-referrer`});if(!i.ok)throw Error(`GIBS: HTTP ${i.status}`);let a=qn(await i.text()).filter(e=>e<=t).slice(-r);if(!a.length)throw Error(`GIBS: no frames`);return Jn.set(e.id,{at:t,times:a}),a}finally{Yn.delete(e.id)}})(),Yn.set(e.id,a)),a}var Zn=[0,1,2];function Qn(e){return new Date(e).getUTCHours()>=9?0:1}function $n(e,t){return Hn(e-t*Rn)}var er=(function(){let e=typeof document<`u`&&document.createElement(`link`).relList;return e&&e.supports&&e.supports(`modulepreload`)?`modulepreload`:`preload`})(),tr=function(e,t){return new URL(e,t).href},nr={},rr=function(e){return e.pathname.endsWith(`.css`)},ir=function(e,t,n){if(t in e)return e[t];let r=n();if(!r){e[t]=void 0;return}let i=r.then(()=>{e[t]=void 0},n=>{throw e[t]=void 0,n});return e[t]=i,i},ar=function(e,t,n){let r=Promise.resolve();if(t&&t.length>0){let e,i=document.querySelector(`meta[property=csp-nonce]`),a=i?.nonce||i?.getAttribute(`nonce`);function o(e){return Promise.all(e.map(e=>Promise.resolve(e).then(e=>({status:`fulfilled`,value:e}),e=>({status:`rejected`,reason:e}))))}function s(e){return import.meta.resolve?new URL(import.meta.resolve(e)):new URL(e,import.meta.url)}r=o(t.map(t=>{t=tr(t,n);let r=s(t),i=rr(r);return ir(nr,r.href,()=>{if(e===void 0){e={all:new Set,styles:new Set};let t=document.getElementsByTagName(`link`);for(let n=t.length-1;n>=0;n--){let r=t[n];e.all.add(r.href),r.rel===`stylesheet`&&e.styles.add(r.href)}}if((i?e.styles:e.all).has(r.href))return;let t=document.createElement(`link`);if(t.rel=i?`stylesheet`:er,i||(t.as=`script`),t.crossOrigin=``,t.href=r.href,a&&t.setAttribute(`nonce`,a),document.head.appendChild(t),i)return new Promise((e,n)=>{t.addEventListener(`load`,e),t.addEventListener(`error`,()=>n(Error(`Unable to preload CSS for ${r}`)))})})}).filter(e=>e!==void 0))}function i(e){let t=new Event(`vite:preloadError`,{cancelable:!0});if(t.payload=e,window.dispatchEvent(t),!t.defaultPrevented)throw e}return r.then(t=>{for(let e of t||[])e.status===`rejected`&&i(e.reason);return e().catch(i)})},or=.7,sr={radar:`off`,satellite:`off`,cyclones:`off`,cycloneCount:0},cr=[`_config`,`_satelliteHidden`,`_cyclonesHidden`,`_viirsDay`],lr,ur=()=>lr??=ar(()=>import(`./ausnz-disaster-leaflet-map-oFUjKiCT.js`),[],import.meta.url),dr=class extends H{static properties={...H.properties,_status:{state:!0},_loadError:{state:!0},_satelliteHidden:{state:!0},_cyclonesHidden:{state:!0},_viirsDay:{state:!0}};static styles=[...H.styles,_`
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
    `];titleKey=`map.title`;usesIncidents=!0;_map;_container;_creating=!1;_resizeObserver;_intersectionObserver;_reducedMotion=typeof matchMedia==`function`&&matchMedia(`(prefers-reduced-motion: reduce)`).matches;constructor(){super(),this._status=sr,this._loadError=!1,this._satelliteHidden=!1,this._cyclonesHidden=!1,this._viirsDay=Qn(Date.now())}static validateConfig(e){super.validateConfig(e);let t=e;q(t,`zoom`,1,18),wt(t,`radar`),Ct(t,`radar_opacity`,.1,1),Tt(t,`satellite_layer`,jn),wt(t,`show_cyclone_tracks`)}static getConfigForm(){return{schema:[...W(),{name:`zoom`,selector:{number:{min:1,max:18,mode:`box`}}},{name:`radar`,default:!0,selector:{boolean:{}}},{name:`radar_opacity`,selector:{number:{min:.1,max:1,step:.05,mode:`slider`}}},{name:`satellite_layer`,default:`none`,selector:{select:{mode:`dropdown`,options:jn.map(e=>({value:e,label:f(void 0,fr(e))}))}}},{name:`show_cyclone_tracks`,default:!1,selector:{boolean:{}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getGridOptions(){return{columns:12,rows:6,min_columns:6,min_rows:4}}getCardSize(){return 7}trackedHomeId=`zone.home`;trackedEntityIds(e){let t=[...super.trackedEntityIds(e),this.trackedHomeId],n=this._config?.show_cyclone_tracks?this.alertsEntityId(e):void 0;return n&&t.push(n),t}alertsEntityId(e){return lt(e,this.deviceId,n.regionalDisasterAlerts)}connectedCallback(){super.connectedCallback(),this.hasUpdated&&this.ensureMap()}disconnectedCallback(){super.disconnectedCallback(),this.teardown()}teardown(){this._resizeObserver?.disconnect(),this._intersectionObserver?.disconnect(),this._resizeObserver=void 0,this._intersectionObserver=void 0,this._map?.destroy(),this._map=void 0,this._container=void 0}updated(e){super.updated(e),this._map&&this.renderRoot.querySelector(`.map`)!==this._container&&this.teardown(),this._map?(e.has(`hass`)||cr.some(t=>e.has(t)))&&this._map.update(this.viewOptions()):this.ensureMap()}viewOptions(){let e=this.hass,t=ft(e,this.entryId).flatMap(t=>{let n=Z(t.attributes.latitude),r=Z(t.attributes.longitude);if(n===void 0||r===void 0)return[];let i=on(t.attributes.warning_level);return[{id:t.entity_id,title:pt(t),levelLabel:f(e,hn[i.level]),tone:i.tone,latitude:n,longitude:r,agency:Q(t.attributes.responsible_agency)??Q(t.attributes.agency)}]}),n=e.states[this.trackedHomeId],r=Z(n?.attributes.latitude),i=Z(n?.attributes.longitude),a=r!==void 0&&i!==void 0?{latitude:r,longitude:i,radius:Z(n?.attributes.radius),label:f(e,`map.home`)}:Number.isFinite(e.config?.latitude)&&Number.isFinite(e.config?.longitude)?{latitude:e.config.latitude,longitude:e.config.longitude,label:f(e,`map.home`)}:void 0,o=this._config?.satellite_layer??`none`,s=this._config?.show_cyclone_tracks&&!this._cyclonesHidden?this.alertsEntityId(e):void 0;return{incidents:t,home:a,darkMode:!!e.themes?.darkMode,zoom:this._config?.zoom,radar:this._config?.radar!==!1,radarOpacity:this._config?.radar_opacity??or,satellite:this._satelliteHidden?`none`:o,viirsDay:this._viirsDay,cyclones:s?xn(e.states[s]?.attributes.alerts):[]}}async ensureMap(){if(this._map||this._creating||!this.hass||!this.isConnected)return;let e=this.renderRoot.querySelector(`.map`);if(e){this._creating=!0;try{let t=await ur(),n=this.renderRoot;if(!n.adoptedStyleSheets.some(e=>e.leaflet)){let e=new CSSStyleSheet;e.replaceSync(t.leafletCss),e.leaflet=!0,n.adoptedStyleSheets=[e,...n.adoptedStyleSheets]}if(!this.isConnected||this._map||!e.isConnected)return;this._container=e,this._map=new t.IncidentMap(e,this.hass.connection,e=>this._status=e,e=>this.moreInfo(e),this._reducedMotion),this._resizeObserver=new ResizeObserver(()=>this._map?.invalidateSize()),this._resizeObserver.observe(e),this._intersectionObserver=new IntersectionObserver(e=>this._map?.setVisible(e.some(e=>e.isIntersecting))),this._intersectionObserver.observe(this),this._map.update(this.viewOptions())}catch(e){console.error(`Disaster Watch map failed to load`,e),this._loadError=!0}finally{this._creating=!1}}}togglePlay(){let e=!this._status.frame?.playing;this._map?.setPlaying(e)}renderRadarBar(e){let t=this._status.frame;if(!t)return k;let n=Lt(e,t.time,{timeStyle:`short`}),r=X(e,t.time),i=t.playing,a=t.source===`radar`,o=a?f(e,i?`map.pause`:`map.play`):f(e,i?`map.pause_satellite`:`map.play_satellite`),s=f(e,a?`map.radar_at`:`map.satellite_at`,{time:n??``});return D`<div class="radar-bar">
      <ha-icon-button .label=${o} aria-pressed=${i?`true`:`false`} @click=${this.togglePlay}>
        <ha-icon .icon=${i?`mdi:pause`:`mdi:play`}></ha-icon>
      </ha-icon-button>
      <span class="time" aria-live=${i?`off`:`polite`}>${s}${r?` · ${r}`:``}</span>
      <span class="frames" aria-hidden="true">
        ${Array.from({length:t.count},(e,n)=>D`<span class=${n===t.index?`current`:``}></span>`)}
      </span>
    </div>`}renderLayerChips(e,t){let n=t.satellite_layer??`none`;if(n===`none`&&!t.show_cyclone_tracks)return k;let r=n===`viirs_truecolor`&&!this._satelliteHidden,i=new Intl.DateTimeFormat(At(e),{day:`numeric`,month:`short`,timeZone:`UTC`}),a=Date.now();return D`<div class="layers">
      <ha-chip-set aria-label=${f(e,`map.layers`)}>
        ${n===`none`?k:D`<ha-filter-chip
                .selected=${!this._satelliteHidden}
                .label=${f(e,fr(n))}
                @click=${e=>{e.preventDefault(),this._satelliteHidden=!this._satelliteHidden}}
              >
                <ha-icon slot="icon" icon="mdi:satellite-variant"></ha-icon>
              </ha-filter-chip>`}
        ${r?Zn.map(t=>{let n=i.format(Date.parse($n(a,t)));return D`<ha-filter-chip
        no-leading-icon
        .selected=${this._viirsDay===t}
        .label=${n}
        title=${`${f(e,`map.viirs_days`)}: ${n}`}
        @click=${e=>{e.preventDefault(),this._viirsDay=t}}
      ></ha-filter-chip>`}):k}
        ${t.show_cyclone_tracks?D`<ha-filter-chip
                .selected=${!this._cyclonesHidden}
                .label=${f(e,`map.cyclones`)}
                @click=${e=>{e.preventDefault(),this._cyclonesHidden=!this._cyclonesHidden}}
              >
                <ha-icon slot="icon" icon="mdi:weather-hurricane"></ha-icon>
              </ha-filter-chip>`:k}
      </ha-chip-set>
    </div>`}renderNotices(e){let t=this._status,n=t=>D`<div class="notice">${I(`info`,f(e,t))}</div>`,r=[];return t.radar===`unavailable`&&r.push(n(`map.radar_unavailable`)),t.satellite===`unavailable`&&r.push(n(`map.satellite_unavailable`)),t.cyclones===`unavailable`&&r.push(n(`map.cyclones_unavailable`)),r}renderBody(e,t){let n=ct(e,this.deviceId)??e.config?.location_name??``;return D`${L({title:this.cardTitle(),icon:`mdi:map-marker-radius`})}
      <div class="map-wrap">
        <div class="map" role="region" aria-label=${f(e,`map.label`,{name:n})}></div>
      </div>
      ${this.renderLayerChips(e,t)}
      ${this.renderRadarBar(e)}
      ${this._status.cyclones===`ok`&&this._status.cycloneCount>0?D`<p class="legend">${f(e,`map.cyclone_legend`)}</p>`:k}
      ${this.renderNotices(e)}
      ${this._loadError?D`<div class="notice">${I(`error`,f(e,`state.unavailable`))}</div>`:k}`}};function fr(e){return e===`none`?`editor.satellite_layer.none`:`map.layer.${e}`}function pr(e,t){return(J(e)?void 0:Z(e?.state))??Z(t)}var mr=8,hr=class extends H{static properties={...H.properties,_expanded:{state:!0}};titleKey=`outages.title`;constructor(){super(),this._expanded=!1}entityKeys(){return[n.powerOutagesCount,n.powerOutagesCustomersAffected]}static validateConfig(e){super.validateConfig(e),q(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}renderBody(e,t){let r=V(e,this.deviceId,n.powerOutagesCount),i=L({title:this.cardTitle(),icon:`mdi:transmission-tower-off`,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(J(r))return D`${i}<div class="content">
          ${I(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let a=$(r.attributes.outages),o=Z(r.state)??a.length,s=pr(V(e,this.deviceId,n.powerOutagesCustomersAffected),r.attributes.customers_affected),c=t.max_items??mr,l=this._expanded?a:a.slice(0,c);return D`${i}
      <div class="content">
        ${o===0?F(`mdi:transmission-tower`,f(e,`outages.empty`)):D`<span class="secondary"
                  >${[p(e,`outages.count`,o,Y(e,o)),s===void 0?void 0:p(e,`outages.customers_affected`,s,Y(e,s))].filter(Boolean).join(` · `)}</span
                >
                ${z(l.map(t=>{let n=Lt(e,t.restore_time,{weekday:`short`,hour:`numeric`,minute:`2-digit`})??Q(t.restore_time),r=Z(t.customers_affected);return R({icon:`mdi:transmission-tower-off`,tone:`amber`,headline:Q(t.suburb)??`—`,supporting:[Q(t.cause),n?f(e,`outages.restore`,{time:n}):void 0].filter(Boolean).join(` · `)||void 0,trailing:r===void 0?void 0:D`<span class="secondary"
                              >${p(e,`outages.customers`,r,Y(e,r))}</span
                            >`})}),this.cardTitle())}
                ${a.length>c?nt(e,this._expanded,a.length,()=>this._expanded=!this._expanded):k}`}
      </div>`}},gr=[{key:`evacuation_centre`,icon:`mdi:home-group`},{key:`place_of_refuge`,icon:`mdi:home-heart`},{key:`sandbag_station`,icon:`mdi:sack`},{key:`other`,icon:`mdi:home-alert`}];function _r(e){return e===`evacuation_centre`||e===`place_of_refuge`||e===`sandbag_station`?e:`other`}var vr=class extends H{titleKey=`relief.title`;entityKeys(){return[n.reliefFacilitiesCount,n.highestWarningLevel,n.weatherWarningsCount]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 5}renderBody(e,t){let r=V(e,this.deviceId,n.reliefFacilitiesCount),i=V(e,this.deviceId,n.highestWarningLevel),a=V(e,this.deviceId,n.weatherWarningsCount),o=L({title:this.cardTitle(),icon:`mdi:home-heart`,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(J(r))return D`${o}<div class="content">
          ${I(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let s=$(r.attributes.facilities).sort((e,t)=>(Z(e.distance_km)??1/0)-(Z(t.distance_km)??1/0)),c=$(i?.attributes.nearby_councils??a?.attributes.nearby_councils).filter(e=>Q(e.name)||Q(e.url));return D`${o}
      <div class="content">
        ${s.length===0?F(`mdi:home-search-outline`,f(e,`relief.empty`)):k}
        ${gr.map(({key:t,icon:n})=>{let r=s.filter(e=>_r(e.facility_type)===t);if(!r.length)return k;let i=f(e,`relief.group.${t}`);return D`<h3 class="list-title">${i}</h3>
            ${z(r.map(t=>{let r=(Q(t.status)??`Open`).toLowerCase()!==`closed`,a=Q(t.name)??i;return R({icon:n,tone:r?`green`:`grey`,headline:a,supporting:Q(t.address)??Q(t.suburb),badge:P(f(e,r?`relief.open`:`relief.closed`),r?`green`:`grey`,r?`mdi:door-open`:`mdi:door-closed`),trailing:Pt(e,Z(t.distance_km))})}),i)}`})}
        ${c.length?D`<h3 class="list-title">${f(e,`relief.councils`)}</h3>
                ${z(c.map(t=>{let n=Q(t.name)??Q(t.url)??``,r=Rt(t.url);return R({icon:`mdi:view-dashboard-outline`,tone:`blue`,headline:n,supporting:r?new URL(r).hostname:void 0,link:r,linkLabel:`${f(e,`action.open_link`)}: ${n}`})}),f(e,`relief.councils`))}`:k}
      </div>`}},yr=8,br=class extends H{static properties={...H.properties,_expanded:{state:!0}};titleKey=`roads.title`;constructor(){super(),this._expanded=!1}entityKeys(){return[n.roadClosuresCount]}static validateConfig(e){super.validateConfig(e),q(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}renderBody(e,t){let r=V(e,this.deviceId,n.roadClosuresCount),i=J(r),a=i?[]:$(r.attributes.closures),o=i?void 0:Z(r.state)??a.length,s=L({title:this.cardTitle(),icon:`mdi:traffic-cone`,count:o?String(o):void 0,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(i)return D`${s}<div class="content">
          ${I(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let c=[...a].sort((e,t)=>(Z(e.distance_km)??1/0)-(Z(t.distance_km)??1/0)),l=t.max_items??yr,u=this._expanded?c:c.slice(0,l);return D`${s}
      <div class="content">
        ${c.length?z(u.map(t=>{let n=Q(t.status)??`—`,r=Xt(n),i=X(e,t.updated_at);return R({icon:Zt(n),tone:r,headline:[Q(t.road),Q(t.suburb)].filter(Boolean).join(`, `)||n,supporting:[Q(t.advice)??Q(t.description)??Q(t.reason),i].filter(Boolean).join(` · `)||void 0,badge:P(n,r),trailing:Pt(e,Z(t.distance_km))})}),this.cardTitle()):F(`mdi:road-variant`,f(e,`roads.empty`))}
        ${c.length>l?nt(e,this._expanded,c.length,()=>this._expanded=!this._expanded):k}
      </div>`}},xr=[{key:n.emergencyWarningNearby,icon:`mdi:alert-octagon`,label:`status.chip.emergency_warning_nearby`},{key:n.activeHazardsNearby,icon:`mdi:alert`,label:`status.chip.active_hazards_nearby`},{key:n.powerOutageActive,icon:`mdi:transmission-tower-off`,label:`status.chip.power_outage_active`},{key:n.roadClosureNearby,icon:`mdi:traffic-cone`,label:`status.chip.road_closure_nearby`}],Sr={all_clear:`status.all_clear`,unavailable:`status.unavailable`,emergency:`status.level.emergency`,watch_and_act:`status.level.watch_and_act`,advice:`status.level.advice`,information:`status.level.information`,unknown:`status.level.unknown`},Cr=class extends H{static styles=[...H.styles,_`
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
    `];titleKey=`card.status.name`;entityKeys(){return[n.highestWarningLevel,n.activeHazardsCount,n.nearestHazardDistance,n.nearestHazardTitle,...xr.map(e=>e.key)]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}getCardSize(){return 2}renderBody(e,t){let r=this.deviceId,i=V(e,r,n.highestWarningLevel),a=V(e,r,n.activeHazardsCount),o=J(a)?void 0:Z(a?.state),s=sn(J(i)?void 0:i?.state,o),c=cn(s),l=f(e,Sr[s]),u=V(e,r,n.nearestHazardDistance),d=V(e,r,n.nearestHazardTitle),ee=J(u)?void 0:Z(u?.state),p=Q(u?.attributes.title)??(J(d)||d?.state===`None`?void 0:Q(d?.state)),m=``;s!==`unavailable`&&o!==void 0&&(m=o===0?f(e,`status.no_hazards`):o===1?f(e,`status.hazard`):f(e,`status.hazards`,{count:o}));let h=Pt(e,ee),g=o&&h?`${f(e,`status.nearest`,{distance:h})}${p?` — ${p}`:``}`:void 0,te=xr.map(t=>({...t,stateObj:V(e,r,t.key)})).filter(e=>e.stateObj?.state===`on`);return D`<div class="content status">
      <button
        class="plain hero"
        aria-label=${`${l}. ${m}${g?`, ${g}`:``}. ${f(e,`action.details`)}`}
        @click=${()=>this.moreInfo(i?.entity_id)}
      >
        <span class="bubble large" style=${Qe({"--tone":$e(c.tone)})} aria-hidden="true">
          <ha-icon .icon=${c.icon}></ha-icon>
        </span>
        <span class="hero-text">
          <span class="level">${l}</span>
          ${m?D`<span class="summary">${m}</span>`:k}
          ${g?D`<span class="summary nearest">${g}</span>`:k}
        </span>
      </button>
      ${te.length?D`<ha-chip-set aria-label=${f(e,`status.alerts`)}>
              ${te.map(t=>D`<ha-assist-chip
                  filled
                  .label=${f(e,t.label)}
                  @click=${()=>this.moreInfo(t.stateObj?.entity_id)}
                >
                  <ha-icon slot="icon" .icon=${t.icon}></ha-icon>
                </ha-assist-chip>`)}
            </ha-chip-set>`:k}
    </div>`}},wr=8,Tr={status:Cr,incidents:gn,warnings:class extends H{static properties={...H.properties,_view:{state:!0},_expanded:{state:!0}};titleKey=`warnings.title`;constructor(){super(),this._view=`warnings`,this._expanded=!1}entityKeys(){return[n.weatherWarningsCount,n.highestWarningLevel]}static validateConfig(e){super.validateConfig(e),q(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 5}renderItem(e,t,n){let r=Q(t.title)??``,i=X(e,t.pub_date),a=Q(t.locations)??Q(t.description);return R({icon:n,tone:this._view===`warnings`?`orange`:`blue`,headline:r,supporting:[a,i].filter(Boolean).join(` · `)||void 0,link:Rt(t.link),linkLabel:`${f(e,`action.open_link`)}: ${r}`})}renderBody(e,t){let r=V(e,this.deviceId,n.weatherWarningsCount),i=V(e,this.deviceId,n.highestWarningLevel),a=J(r),o=$(r?.attributes.warnings),s=$(r?.attributes.emergency_news??i?.attributes.emergency_news),c=a?0:Z(r?.state)??o.length,l=this._view===`warnings`?o:s,u=t.max_items??wr,d=this._expanded?l:l.slice(0,u),ee=this._view===`warnings`?`mdi:weather-lightning-rainy`:`mdi:newspaper-variant-outline`,p=(e,t)=>D`<ha-filter-chip
      no-leading-icon
      .selected=${this._view===e}
      .label=${t}
      @click=${t=>{t.preventDefault(),this._view=e,this._expanded=!1}}
    ></ha-filter-chip>`;return D`${L({title:this.cardTitle(),icon:`mdi:weather-lightning-rainy`,detailsLabel:f(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0})}
      <div class="content">
        ${a?I(`warning`,f(e,r?`state.unavailable`:`state.entity_missing`)):D`<ha-chip-set aria-label=${f(e,`warnings.views`)}>
                  ${p(`warnings`,f(e,`warnings.tab.warnings`,{count:c}))}
                  ${p(`news`,f(e,`warnings.tab.news`,{count:s.length}))}
                </ha-chip-set>
                ${d.length?z(d.map(t=>this.renderItem(e,t,ee))):F(`mdi:check-circle-outline`,f(e,this._view===`warnings`?`warnings.empty`:`warnings.news_empty`))}
                ${l.length>u?nt(e,this._expanded,l.length,()=>this._expanded=!this._expanded):k}
`}
      </div>`}},fire_danger:nn,outages:hr,roads:br,conditions:tn,relief:vr,cameras:Vt,map:dr},Er=[{tag:i,ctor:Ot,key:`all`},...Object.keys(Tr).map(e=>({tag:r[e],ctor:Tr[e],key:e}))];window.customCards=window.customCards||[];for(let{tag:e,ctor:n,key:r}of Er)customElements.get(e)||customElements.define(e,n),window.customCards.some(t=>t.type===e)||window.customCards.push({type:e,name:f(void 0,`card.${r}.name`),description:f(void 0,`card.${r}.description`),preview:!0,documentationURL:t});export{$n as a,Vn as i,Xn as n,_n as o,Wn as r,kn as s,Fn as t};
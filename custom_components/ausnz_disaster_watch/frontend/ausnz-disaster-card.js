var e=`ausnz_disaster_watch`,t=`https://github.com/tinkerologie/ha-ausnz-disaster-watch#dashboard-cards`,n={emergencyWarningNearby:`emergency_warning_nearby`,activeHazardsNearby:`active_hazards_nearby`,powerOutageActive:`power_outage_active`,roadClosureNearby:`road_closure_nearby`,nearestHazardDistance:`nearest_hazard_distance`,activeHazardsCount:`active_hazards_count`,highestWarningLevel:`highest_warning_level`,nearestHazardTitle:`nearest_hazard_title`,powerOutagesCount:`power_outages_count`,powerOutagesCustomersAffected:`power_outages_customers_affected`,roadClosuresCount:`road_closures_count`,weatherWarningsCount:`weather_warnings_count`,fireDangerRating:`fire_danger_rating`,airQualityRating:`air_quality_rating`,primaryWeatherObservation:`primary_weather_observation`,reliefFacilitiesCount:`relief_facilities_count`},r={status:`ausnz-disaster-status-card`,incidents:`ausnz-disaster-incidents-card`,warnings:`ausnz-disaster-warnings-card`,fire_danger:`ausnz-disaster-fire-danger-card`,outages:`ausnz-disaster-outages-card`,roads:`ausnz-disaster-roads-card`,conditions:`ausnz-disaster-conditions-card`,relief:`ausnz-disaster-relief-card`,cameras:`ausnz-disaster-cameras-card`,map:`ausnz-disaster-map-card`},i=`ausnz-disaster-card`,a=[`status`,`incidents`,`warnings`,`fire_danger`,`roads`,`outages`],o=Object.keys(r),s={"card.status.name":`Disaster Watch status`,"card.status.description":`Headline warning level, hazard count, nearest hazard and active alerts.`,"card.incidents.name":`Disaster Watch incidents`,"card.incidents.description":`Incidents nearest first, with category filters and Australian Warning System levels.`,"card.warnings.name":`Disaster Watch warnings`,"card.warnings.description":`Weather warnings and emergency news.`,"card.fire_danger.name":`Disaster Watch fire danger`,"card.fire_danger.description":`Fire danger rating on the AFDRS scale, district and total fire ban.`,"card.outages.name":`Disaster Watch power outages`,"card.outages.description":`Power outages and customers affected.`,"card.roads.name":`Disaster Watch roads`,"card.roads.description":`Road closures and hazards.`,"card.conditions.name":`Disaster Watch conditions`,"card.conditions.description":`Local weather observation and air quality.`,"card.relief.name":`Disaster Watch relief`,"card.relief.description":`Evacuation centres, places of refuge, sandbag stations and council dashboards.`,"card.cameras.name":`Disaster Watch cameras`,"card.cameras.description":`Flood and traffic camera snapshots.`,"card.map.name":`Disaster Watch map`,"card.map.description":`Map of incidents with animated rain radar.`,"card.all.name":`Disaster Watch`,"card.all.description":`All-in-one card: a configurable stack of the Disaster Watch cards.`,"state.not_set_up":`Set up the Australia and New Zealand Disaster Watch integration to use this card.`,"state.device_missing":`The selected Disaster Watch device was not found. Choose another device in the card editor.`,"state.unavailable":`Data is unavailable right now.`,"state.entity_missing":`This Disaster Watch entity is missing or disabled.`,"action.details":`Show details`,"action.open_link":`Open source page`,"action.show_all":`Show all {count}`,"action.show_less":`Show less`,"status.all_clear":`All clear`,"status.unavailable":`Status unavailable`,"status.level.emergency":`Emergency Warning`,"status.level.watch_and_act":`Watch and Act`,"status.level.advice":`Advice`,"status.level.information":`Information`,"status.level.unknown":`Level unknown`,"status.hazards":`{count} hazards nearby`,"status.hazard":`1 hazard nearby`,"status.no_hazards":`No hazards nearby`,"status.nearest":`nearest {distance}`,"status.chip.emergency_warning_nearby":`Emergency warning`,"status.chip.active_hazards_nearby":`Hazards nearby`,"status.chip.power_outage_active":`Power outage`,"status.chip.road_closure_nearby":`Road closure`,"status.alerts":`Active alerts`,"incidents.title":`Incidents`,"incidents.empty":`No incidents nearby.`,"incidents.empty_filtered":`No incidents in this category.`,"incidents.filters":`Incident filters`,"incidents.category.all":`All`,"incidents.category.fire":`Fire`,"incidents.category.flood_storm":`Flood & storm`,"incidents.category.geological":`Geological`,"incidents.category.roads":`Roads`,"incidents.category.other":`Other`,"incidents.planned_burns":`Planned burns`,"incidents.planned_burn":`Planned burn`,"incidents.updated":`updated {time}`,"warnings.title":`Warnings`,"warnings.tab.warnings":`Warnings ({count})`,"warnings.tab.news":`News ({count})`,"warnings.views":`Warnings or news`,"warnings.empty":`No weather warnings.`,"warnings.news_empty":`No emergency news.`,"fire.title":`Fire danger`,"fire.rating.moderate":`Moderate`,"fire.rating.high":`High`,"fire.rating.extreme":`Extreme`,"fire.rating.catastrophic":`Catastrophic`,"fire.rating.no_rating":`No rating`,"fire.scale":`Fire danger rating scale`,"fire.current":`Current rating`,"fire.forecast_for":`Forecast for {day}`,"fire.total_fire_ban":`Total fire ban`,"fire.no_total_fire_ban":`No total fire ban`,"fire.district":`{district} district`,"outages.title":`Power outages`,"outages.summary":`{count} outages · {customers} customers affected`,"outages.summary_count":`{count} outages`,"outages.empty":`No power outages reported.`,"outages.customers":`{count} customers`,"outages.restore":`Restore {time}`,"roads.title":`Roads`,"roads.empty":`No road closures or hazards.`,"conditions.title":`Conditions`,"conditions.weather":`Weather`,"conditions.air_quality":`Air quality`,"conditions.temperature":`Temperature`,"conditions.feels_like":`Feels like`,"conditions.humidity":`Humidity`,"conditions.wind":`Wind`,"conditions.wind_from":`Wind from {direction}`,"conditions.gust":`Gust`,"conditions.pressure":`Pressure`,"conditions.rain":`Rain since 9 am`,"conditions.station":`Station: {name}`,"conditions.no_weather":`No weather observation.`,"conditions.no_air_quality":`No air quality reading.`,"conditions.aq.good":`Good`,"conditions.aq.fair":`Fair`,"conditions.aq.poor":`Poor`,"conditions.aq.very_poor":`Very poor`,"conditions.aq.extremely_poor":`Extremely poor`,"conditions.aq.unknown":`Unknown`,"relief.title":`Relief`,"relief.empty":`No relief facilities open nearby.`,"relief.group.evacuation_centre":`Evacuation centres`,"relief.group.place_of_refuge":`Places of refuge`,"relief.group.sandbag_station":`Sandbag stations`,"relief.group.other":`Other facilities`,"relief.councils":`Council dashboards`,"relief.open":`Open`,"relief.closed":`Closed`,"cameras.title":`Cameras`,"cameras.empty":`No cameras for this location.`,"cameras.no_image":`No image yet`,"map.title":`Map`,"map.label":`Map of incidents near {name}`,"map.home":`Home`,"map.play":`Play radar animation`,"map.pause":`Pause radar animation`,"map.radar_at":`Radar {time}`,"map.radar_unavailable":`Rain radar is unavailable right now.`,"map.radar_off":`Radar off`,"editor.device":`Disaster Watch location`,"editor.device_helper":`The integration entry (location) this card shows. Defaults to the first one.`,"editor.title":`Title`,"editor.title_helper":`Leave empty for the default title.`,"editor.max_items":`Maximum items`,"editor.max_items_helper":`Rows shown before a Show all button.`,"editor.show_planned_burns":`Show planned burns`,"editor.show_planned_burns_helper":`Planned burns only reach the card when the integration's 'Exclude hazard reduction burns' option is off.`,"editor.categories":`Categories`,"editor.categories_helper":`Incident categories to show. Leave empty for all.`,"editor.refresh_interval":`Refresh interval`,"editor.refresh_interval_helper":`Seconds between snapshot refreshes while the card is visible.`,"editor.zoom":`Zoom`,"editor.zoom_helper":`Initial zoom. Leave empty to fit all incidents.`,"editor.radar":`Rain radar`,"editor.radar_helper":`Animated RainViewer radar (free for personal use, attribution shown on the map).`,"editor.radar_opacity":`Radar opacity`,"editor.cards":`Sections`,"editor.cards_helper":`Cards to stack, in order.`},c={en:s};function l(e,t,n){let r=e?.locale?.language||e?.language||`en`,i=(c[r]??c[r.split(`-`)[0]??`en`]??s)[t]??s[t]??t;return n?i.replace(/\{(\w+)\}/g,(e,t)=>t in n?String(n[t]):e):i}var u=globalThis,d=u.ShadowRoot&&(u.ShadyCSS===void 0||u.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,f=Symbol(),ee=new WeakMap,p=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==f)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(d&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=ee.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&ee.set(t,e))}return e}toString(){return this.cssText}},m=e=>new p(typeof e==`string`?e:e+``,void 0,f),h=(e,...t)=>new p(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,f),g=(e,t)=>{if(d)e.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let n of t){let t=document.createElement(`style`),r=u.litNonce;r!==void 0&&t.setAttribute(`nonce`,r),t.textContent=n.cssText,e.appendChild(t)}},te=d?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return m(t)})(e):e,{is:ne,defineProperty:re,getOwnPropertyDescriptor:ie,getOwnPropertyNames:ae,getOwnPropertySymbols:oe,getPrototypeOf:se}=Object,ce=globalThis,le=ce.trustedTypes,ue=le?le.emptyScript:``,de=ce.reactiveElementPolyfillSupport,_=(e,t)=>e,fe={toAttribute(e,t){switch(t){case Boolean:e=e?ue:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},pe=(e,t)=>!ne(e,t),me={attribute:!0,type:String,converter:fe,reflect:!1,useDefault:!1,hasChanged:pe};Symbol.metadata??=Symbol(`metadata`),ce.litPropertyMetadata??=new WeakMap;var v=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=me){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&re(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=ie(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??me}static _$Ei(){if(this.hasOwnProperty(_(`elementProperties`)))return;let e=se(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(_(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(_(`properties`))){let e=this.properties,t=[...ae(e),...oe(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(te(e))}else e!==void 0&&t.push(te(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return g(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?fe:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?fe:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??pe)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};v.elementStyles=[],v.shadowRootOptions={mode:`open`},v[_(`elementProperties`)]=new Map,v[_(`finalized`)]=new Map,de?.({ReactiveElement:v}),(ce.reactiveElementVersions??=[]).push(`2.1.2`);var he=globalThis,ge=e=>e,y=he.trustedTypes,_e=y?y.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,ve=`$lit$`,b=`lit$${Math.random().toFixed(9).slice(2)}$`,ye=`?`+b,be=`<${ye}>`,x=document,S=()=>x.createComment(``),C=e=>e===null||typeof e!=`object`&&typeof e!=`function`,xe=Array.isArray,Se=e=>xe(e)||typeof e?.[Symbol.iterator]==`function`,Ce=`[ 	
\f\r]`,w=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,we=/-->/g,Te=/>/g,T=RegExp(`>|${Ce}(?:([^\\s"'>=/]+)(${Ce}*=${Ce}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),Ee=/'/g,De=/"/g,Oe=/^(?:script|style|textarea|title)$/i,E=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),D=Symbol.for(`lit-noChange`),O=Symbol.for(`lit-nothing`),ke=new WeakMap,k=x.createTreeWalker(x,129);function Ae(e,t){if(!xe(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return _e===void 0?t:_e.createHTML(t)}var je=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=w;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===w?c[1]===`!--`?o=we:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=T):(Oe.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=T):o=Te:o===T?c[0]===`>`?(o=i??w,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?T:c[3]===`"`?De:Ee):o===De||o===Ee?o=T:o===we||o===Te?o=w:(o=T,i=void 0);let d=o===T&&e[t+1].startsWith(`/>`)?` `:``;a+=o===w?n+be:l>=0?(r.push(s),n.slice(0,l)+ve+n.slice(l)+b+d):n+b+(l===-2?t:d)}return[Ae(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},Me=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=je(t,n);if(this.el=e.createElement(l,r),k.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=k.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(ve)){let t=u[o++],n=i.getAttribute(e).split(b),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?Fe:r[1]===`?`?Ie:r[1]===`@`?Le:j}),i.removeAttribute(e)}else e.startsWith(b)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(Oe.test(i.tagName)){let e=i.textContent.split(b),t=e.length-1;if(t>0){i.textContent=y?y.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],S()),k.nextNode(),c.push({type:2,index:++a});i.append(e[t],S())}}}else if(i.nodeType===8){if(i.data===ye)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(b,e+1))!==-1;)c.push({type:7,index:a}),e+=b.length-1}}a++}}static createElement(e,t){let n=x.createElement(`template`);return n.innerHTML=e,n}};function A(e,t,n=e,r){if(t===D)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=C(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=A(e,i._$AS(e,t.values),i,r)),t}var Ne=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??x).importNode(t,!0);k.currentNode=r;let i=k.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new Pe(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Re(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=k.nextNode(),a++)}return k.currentNode=x,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},Pe=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=O,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=A(this,e,t),C(e)?e===O||e==null||e===``?(this._$AH!==O&&this._$AR(),this._$AH=O):e!==this._$AH&&e!==D&&this._(e):e._$litType$===void 0?e.nodeType===void 0?Se(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==O&&C(this._$AH)?this._$AA.nextSibling.data=e:this.T(x.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=Me.createElement(Ae(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new Ne(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=ke.get(e.strings);return t===void 0&&ke.set(e.strings,t=new Me(e)),t}k(t){xe(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(S()),this.O(S()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=ge(e).nextSibling;ge(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},j=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=O,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=O}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=A(this,e,t,0),a=!C(e)||e!==this._$AH&&e!==D,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=A(this,r[n+o],t,o),s===D&&(s=this._$AH[o]),a||=!C(s)||s!==this._$AH[o],s===O?e=O:e!==O&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===O?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},Fe=class extends j{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===O?void 0:e}},Ie=class extends j{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==O)}},Le=class extends j{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=A(this,e,t,0)??O)===D)return;let n=this._$AH,r=e===O&&n!==O||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==O&&(n===O||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Re=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){A(this,e)}},ze=he.litHtmlPolyfillSupport;ze?.(Me,Pe),(he.litHtmlVersions??=[]).push(`3.3.3`);var Be=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new Pe(t.insertBefore(S(),e),e,void 0,n??{})}return i._$AI(e),i},Ve=globalThis,M=class extends v{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Be(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return D}};M._$litElement$=!0,M.finalized=!0,Ve.litElementHydrateSupport?.({LitElement:M});var He=Ve.litElementPolyfillSupport;He?.({LitElement:M}),(Ve.litElementVersions??=[]).push(`4.2.2`);var Ue={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},We=e=>(...t)=>({_$litDirective$:e,values:t}),Ge=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},Ke=`important`,qe=` !`+Ke,N=We(class extends Ge{constructor(e){if(super(e),e.type!==Ue.ATTRIBUTE||e.name!==`style`||e.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(e){return Object.keys(e).reduce((t,n)=>{let r=e[n];return r==null?t:t+`${n=n.includes(`-`)?n:n.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,`-$&`).toLowerCase()}:${r};`},``)}update(e,[t]){let{style:n}=e.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let e of this.ft)t[e]??(this.ft.delete(e),e.includes(`-`)?n.removeProperty(e):n[e]=null);for(let e in t){let r=t[e];if(r!=null){this.ft.add(e);let t=typeof r==`string`&&r.endsWith(qe);e.includes(`-`)||t?n.setProperty(e,t?r.slice(0,-11):r,t?Ke:``):n[e]=r}}return D}});function Je(e){return`var(--${e}-color)`}var Ye=e=>N({"--tone":Je(e)});function Xe(e,t,n=!1){return E`<span class="bubble ${n?`large`:``}" style=${Ye(t)} aria-hidden="true">
    <ha-icon .icon=${e}></ha-icon>
  </span>`}function P(e,t,n){return E`<span class="badge" style=${Ye(t)}>
    ${n?E`<ha-icon .icon=${n} aria-hidden="true"></ha-icon>`:O}<span>${e}</span>
  </span>`}function F(e,t){return E`<div class="empty"><ha-icon .icon=${e} aria-hidden="true"></ha-icon><span>${t}</span></div>`}function I(e,t){return E`<ha-alert alert-type=${e}>${t}</ha-alert>`}function L(e){return E`<div class="header">
    <ha-icon .icon=${e.icon} aria-hidden="true"></ha-icon>
    <h2 class="title">${e.title}${e.count?E` <span class="count">${e.count}</span>`:O}</h2>
    ${e.onDetails?E`<div class="actions">
            <ha-icon-button .label=${e.detailsLabel??``} @click=${e.onDetails}>
              <ha-icon icon="mdi:information-outline"></ha-icon>
            </ha-icon-button>
          </div>`:O}
  </div>`}function R(e){return E`<div class="row" role="listitem">
    <ha-md-list-item
      type=${e.onActivate?`button`:`text`}
      @click=${e.onActivate??O}
    >
      <span slot="start">${Xe(e.icon,e.tone)}</span>
      <span slot="headline" class="headline">${e.headline}</span>
      ${e.badge?E`<span slot="supporting-text" class="row-badge">${e.badge}</span>`:O}
      ${e.supporting?E`<span slot="supporting-text" class="supporting">${e.supporting}</span>`:O}
      ${e.trailing?E`<span slot="end" class="trailing">${e.trailing}</span>`:O}
    </ha-md-list-item>
    ${e.link?E`<ha-icon-button
            class="link"
            .label=${e.linkLabel??``}
            .href=${e.link}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ha-icon icon="mdi:open-in-new"></ha-icon>
          </ha-icon-button>`:O}
  </div>`}function z(e,t){return E`<div class="list" role="list" aria-label=${t??O}>${e}</div>`}function Ze(e,t,n,r){return E`<ha-button
    class="more"
    appearance="plain"
    size="s"
    aria-expanded=${t?`true`:`false`}
    @click=${r}
    >${t?l(e,`action.show_less`):l(e,`action.show_all`,{count:n})}</ha-button
  >`}var Qe=new WeakMap;function $e(e){let t=e.entities,n=Qe.get(t);if(n)return n;let r=new Map,i=new Map;for(let t of Object.values(e.entities??{}))if(t.platform===`ausnz_disaster_watch`&&t.device_id){if(t.translation_key){let e=r.get(t.device_id);e||r.set(t.device_id,e=new Map),e.set(t.translation_key,t.entity_id)}if(t.entity_id.startsWith(`camera.`)){let e=i.get(t.device_id)??[];e.push(t.entity_id),i.set(t.device_id,e)}}let a=new Set([...r.keys(),...i.keys()]),o=Object.keys(e.devices??{}).filter(e=>a.has(e));for(let e of a)o.includes(e)||o.push(e);let s={devices:o,byKey:r,cameras:i};return Qe.set(t,s),s}function B(e){return $e(e).devices}function et(e,t){return t||B(e)[0]}function tt(e,t){return!!t&&B(e).includes(t)}function nt(t,n){if(!n)return;let r=t.devices?.[n];if(!r)return;let i=r.identifiers?.find(([t])=>t===e);return i?i[1]:r.config_entries?.[0]}function rt(e,t){if(!t)return;let n=e.devices?.[t];return n?.name_by_user||n?.name||void 0}function it(e,t,n){if(t)return $e(e).byKey.get(t)?.get(n)}function V(e,t,n){let r=it(e,t,n);return r?e.states[r]:void 0}function at(e,t){return t?[...$e(e).cameras.get(t)??[]].sort((t,n)=>{let r=String(e.states[t]?.attributes.friendly_name??t),i=String(e.states[n]?.attributes.friendly_name??n);return r.localeCompare(i)}):[]}var ot=new WeakMap;function st(e,t){if(!t)return[];let n=ot.get(e.states);n||ot.set(e.states,n=new Map);let r=n.get(t);if(r)return r;let i=Object.values(e.states).filter(e=>e.entity_id.startsWith(`geo_location.`)&&e.attributes.integration===`ausnz_disaster_watch`&&e.attributes.entry_id===t).sort((e,t)=>(lt(e)??1/0)-(lt(t)??1/0));return n.set(t,i),i}function ct(e){let t=e.attributes.title??e.attributes.friendly_name;return typeof t==`string`&&t?t:e.entity_id}function lt(e){let t=Number.parseFloat(e.state);if(Number.isFinite(t))return t;let n=e.attributes.distance_km;return typeof n==`number`&&Number.isFinite(n)?n:void 0}var ut=[`ha-card`,`ha-icon`,`ha-icon-button`,`ha-button`,`ha-alert`,`ha-assist-chip`,`ha-filter-chip`,`ha-chip-set`,`ha-md-list-item`,`ha-tooltip`],dt;function ft(e=5e3){return dt??=(async()=>{try{await window.loadCardHelpers?.()}catch{}await Promise.race([Promise.all(ut.map(e=>customElements.whenDefined(e))),new Promise(t=>setTimeout(t,e))])})(),dt}var pt=h`
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
`;function mt(e,t,n){e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0}))}function ht(e,t){t&&mt(e,`hass-more-info`,{entityId:t})}var H=class extends M{static properties={hass:{attribute:!1},embedded:{type:Boolean,reflect:!0},_config:{state:!0}};static styles=[pt];constructor(){super(),this.embedded=!1}entityKeys(){return[]}usesIncidents=!1;extraEntityIds(e){return[]}static validateConfig(e){if(!e||typeof e!=`object`)throw Error(`Invalid configuration`);if(e.device!==void 0&&typeof e.device!=`string`)throw Error(`'device' must be a device ID`);if(e.title!==void 0&&typeof e.title!=`string`)throw Error(`'title' must be text`)}setConfig(e){this.constructor.validateConfig(e),this._config={...e}}get config(){return this._config}get deviceId(){return this.hass?et(this.hass,this._config?.device):void 0}get entryId(){return this.hass?nt(this.hass,this.deviceId):void 0}entityId(e){return this.hass?it(this.hass,this.deviceId,e):void 0}cardTitle(){return this._config?.title||l(this.hass,this.titleKey)}moreInfo(e){ht(this,e)}trackedEntityIds(e){let t=et(e,this._config?.device),n=[];for(let r of this.entityKeys()){let i=it(e,t,r);i&&n.push(i)}if(this.usesIncidents)for(let r of st(e,nt(e,t)))n.push(r.entity_id);return n.push(...this.extraEntityIds(e)),n}shouldUpdate(e){if(!e.has(`hass`)||e.size>1)return!0;let t=e.get(`hass`),n=this.hass;if(!t||!n||t.entities!==n.entities||t.devices!==n.devices||t.locale!==n.locale||t.themes?.darkMode!==n.themes?.darkMode)return!0;let r=new Set([...this.trackedEntityIds(t),...this.trackedEntityIds(n)]);for(let e of r)if(t.states[e]!==n.states[e])return!0;return!1}connectedCallback(){super.connectedCallback(),ft()}getCardSize(){return 3}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}renderSetupState(e){if(B(e).length===0)return E`<div class="content">${I(`info`,l(e,`state.not_set_up`))}</div>`;if(this._config?.device&&!tt(e,this._config.device))return E`<div class="content">${I(`warning`,l(e,`state.device_missing`))}</div>`}render(){if(!this._config||!this.hass)return O;let e=this.renderSetupState(this.hass)??this.renderBody(this.hass,this._config);return this.embedded?E`<section class="embedded" aria-label=${this.cardTitle()}>${e}</section>`:E`<ha-card>${e}</ha-card>`}};function U(e){let t=e?B(e)[0]:void 0;return t?{device:t}:{}}function W(){return[{name:`device`,selector:{device:{filter:{integration:e}}}},{name:`title`,selector:{text:{}}}]}var gt={device:`editor.device`,title:`editor.title`,max_items:`editor.max_items`,show_planned_burns:`editor.show_planned_burns`,categories:`editor.categories`,refresh_interval:`editor.refresh_interval`,zoom:`editor.zoom`,radar:`editor.radar`,radar_opacity:`editor.radar_opacity`,cards:`editor.cards`},_t={device:`editor.device_helper`,title:`editor.title_helper`,max_items:`editor.max_items_helper`,show_planned_burns:`editor.show_planned_burns_helper`,categories:`editor.categories_helper`,refresh_interval:`editor.refresh_interval_helper`,zoom:`editor.zoom_helper`,radar:`editor.radar_helper`,cards:`editor.cards_helper`},G=e=>{let t=gt[e.name];return t?l(void 0,t):void 0},K=e=>{let t=_t[e.name];return t?l(void 0,t):void 0};function q(e,t,n=1,r=1e3){let i=e[t];if(i!=null&&(typeof i!=`number`||!Number.isInteger(i)||i<n||i>r))throw Error(`'${t}' must be a whole number from ${n} to ${r}`)}function vt(e,t,n,r){let i=e[t];if(i!=null&&(typeof i!=`number`||!Number.isFinite(i)||i<n||i>r))throw Error(`'${t}' must be a number from ${n} to ${r}`)}function yt(e,t){let n=e[t];if(n!==void 0&&typeof n!=`boolean`)throw Error(`'${t}' must be true or false`)}function bt(e,t,n){let r=e[t];if(r!=null&&(!Array.isArray(r)||r.some(e=>typeof e!=`string`||!n.includes(e))))throw Error(`'${t}' must be a list of: ${n.join(`, `)}`)}var xt={status:`card.status.name`,incidents:`card.incidents.name`,warnings:`card.warnings.name`,fire_danger:`card.fire_danger.name`,outages:`card.outages.name`,roads:`card.roads.name`,conditions:`card.conditions.name`,relief:`card.relief.name`,cameras:`card.cameras.name`,map:`card.map.name`},St=class e extends M{static properties={_config:{state:!0}};static styles=[pt,h`
      .title {
        margin: 0;
        padding: var(--ha-space-4) var(--ha-space-4) 0;
        font-family: var(--ha-font-family-heading);
        font-size: var(--ha-font-size-xl);
        font-weight: var(--ha-font-weight-medium);
        line-height: var(--ha-line-height-condensed);
      }
    `];_children=new Map;_hass;set hass(e){let t=e=>!!e&&B(e).length>0;if((t(e)!==t(this._hass)||!this._hass)&&this.requestUpdate(),this._hass=e,e)for(let t of this._children.values())t.hass=e}get hass(){return this._hass}static validateConfig(e){H.validateConfig(e),bt(e,`cards`,o)}static getConfigForm(){return{schema:[...W(),{name:`cards`,selector:{select:{multiple:!0,reorder:!0,mode:`list`,options:o.map(e=>({value:e,label:l(void 0,xt[e])}))}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}setConfig(t){e.validateConfig(t),this._config={...t}}sections(){return this._config?.cards?.length?this._config.cards:a}connectedCallback(){super.connectedCallback(),ft()}getCardSize(){return this.sections().length*3}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}willUpdate(e){if(this._config){if(e.has(`_config`)){let e=new Set(this.sections());for(let t of[...this._children.keys()])e.has(t)||this._children.delete(t);for(let t of e){let e=this._children.get(t);e||(e=document.createElement(r[t]),e.embedded=!0,this._children.set(t,e)),e.setConfig({type:`custom:${r[t]}`,device:this._config.device})}}if(this._hass)for(let e of this._children.values())e.hass=this._hass}}render(){if(!this._config)return O;let e=this.sections().map(e=>this._children.get(e)).filter(e=>!!e);return this._hass&&B(this._hass).length===0?E`<ha-card><div class="content">${I(`info`,l(this._hass,`state.not_set_up`))}</div></ha-card>`:E`<ha-card>
      ${this._config.title?E`<h2 class="title">${this._config.title}</h2>`:O}
      ${e.map((e,t)=>E`${t?E`<hr class="divider" />`:O}${e}`)}
    </ha-card>`}},Ct=new Set([`unavailable`,`unknown`]);function J(e){return!e||Ct.has(e.state)}function wt(e){return e.locale?.language||e.language||`en`}function Tt(e){return e.locale?.time_zone===`server`?e.config?.time_zone:void 0}function Et(e,t){if(e.formatEntityState)return e.formatEntityState(t);let n=t.attributes.unit_of_measurement;return n?`${t.state} ${n}`:t.state}function Dt(e,t,n,r){let i=r===void 0?t.attributes[n]:r;return e.formatEntityAttributeValue?e.formatEntityAttributeValue(t,n,i):typeof i==`number`?Y(e,i):String(i??``)}function Y(e,t,n){try{return new Intl.NumberFormat(wt(e),n).format(t)}catch{return String(t)}}function X(e,t){if(t!=null&&Number.isFinite(t))return`${Y(e,t,{maximumFractionDigits:+(t<10)})} km`}function Ot(e){if(typeof e!=`string`&&typeof e!=`number`)return;let t=typeof e==`string`?/^\/Date\((-?\d+)(?:[+-]\d{4})?\)\/$/.exec(e.trim()):null;if(t)return new Date(Number(t[1]));let n=new Date(e);return Number.isNaN(n.getTime())?void 0:n}var kt=[[`year`,31536e3],[`month`,2592e3],[`week`,604800],[`day`,86400],[`hour`,3600],[`minute`,60],[`second`,1]];function At(e,t,n=Date.now()){let r=Ot(t);if(!r)return;let i=Math.round((r.getTime()-n)/1e3),a=new Intl.RelativeTimeFormat(wt(e),{numeric:`auto`});for(let[e,t]of kt)if(Math.abs(i)>=t||e===`second`)return a.format(Math.round(i/t),e)}function jt(e,t,n={dateStyle:`medium`,timeStyle:`short`}){let r=Ot(t);if(r)try{return new Intl.DateTimeFormat(wt(e),{...n,timeZone:Tt(e)}).format(r)}catch{return r.toISOString()}}function Mt(e){if(typeof e!=`string`||!e.trim())return;let t;try{t=new URL(e.trim())}catch{return}return t.protocol===`http:`||t.protocol===`https:`?t.href:void 0}function Z(e){if(typeof e==`number`)return Number.isFinite(e)?e:void 0;if(typeof e==`string`&&e.trim()!==``){let t=Number(e);return Number.isFinite(t)?t:void 0}}function Q(e){return typeof e==`string`&&e.trim()?e.trim():void 0}function $(e){return Array.isArray(e)?e.filter(e=>e&&typeof e==`object`):[]}var Nt=e=>`/api/camera_proxy/${e}`,Pt=10,Ft=class extends H{static properties={...H.properties,_tick:{state:!0},_failed:{state:!0},_signed:{state:!0}};static styles=[...H.styles,h`
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
    `];_signing=new Set;titleKey=`cameras.title`;_timer;_observer;_visible=!1;_onVisibility=()=>this.updateTimer();constructor(){super(),this._tick=0,this._failed=new Set,this._signed={}}extraEntityIds(e){return at(e,et(e,this.config?.device))}static validateConfig(e){super.validateConfig(e),q(e,`refresh_interval`,Pt,3600)}static getConfigForm(){return{schema:[...W(),{name:`refresh_interval`,selector:{number:{min:Pt,max:3600,step:5,mode:`box`,unit_of_measurement:`s`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 4}connectedCallback(){super.connectedCallback(),document.addEventListener(`visibilitychange`,this._onVisibility),`IntersectionObserver`in window?(this._observer=new IntersectionObserver(e=>{this._visible=e.some(e=>e.isIntersecting),this.updateTimer()}),this._observer.observe(this)):(this._visible=!0,this.updateTimer())}disconnectedCallback(){super.disconnectedCallback(),document.removeEventListener(`visibilitychange`,this._onVisibility),this._observer?.disconnect(),this._observer=void 0,this._visible=!1,this.updateTimer()}updated(e){super.updated(e),this.signMissing(),e.has(`_config`)&&this._timer&&(clearInterval(this._timer),this._timer=void 0,this.updateTimer())}updateTimer(){let e=this._visible&&document.visibilityState===`visible`&&this.isConnected;if(e&&!this._timer){let e=this._config?.refresh_interval??60;this._timer=setInterval(()=>{this._failed=new Set,this._tick+=1},e*1e3)}else!e&&this._timer&&(clearInterval(this._timer),this._timer=void 0)}signMissing(){let e=this.hass;if(e)for(let t of at(e,this.deviceId)){let n=e.states[t];if(!n||J(n)||Q(n.attributes.entity_picture))continue;let r=`${t}@${this._tick}`;this._signed[r]||this._signing.has(r)||(this._signing.add(r),e.connection.sendMessagePromise({type:`auth/sign_path`,path:Nt(t),expires:300}).then(e=>{e?.path&&(this._signed={...this.prune(),[r]:e.path})}).catch(()=>void 0).finally(()=>this._signing.delete(r)))}}prune(){return Object.fromEntries(Object.entries(this._signed).filter(([e])=>e.endsWith(`@${this._tick}`)))}imageUrl(e){return this._tick?`${e}${e.includes(`?`)?`&`:`?`}t=${this._tick}`:e}renderBody(e,t){let n=at(e,this.deviceId);return E`${L({title:this.cardTitle(),icon:`mdi:cctv`,count:n.length?String(n.length):void 0})}
      <div class="content">
        ${n.length?E`<div class="grid" role="list">
                ${n.map(t=>{let n=e.states[t],r=Q(e.entities[t]?.name)??Q(n?.attributes.friendly_name)??t,i=J(n)?void 0:Q(n?.attributes.entity_picture),a=i?this.imageUrl(i):this._signed[`${t}@${this._tick}`],o=a&&!this._failed.has(a);return E`<div role="listitem">
                    <button class="plain camera" aria-label=${`${r}. ${l(e,`action.details`)}`} @click=${()=>this.moreInfo(t)}>
                      <span class="frame">
                        ${o?E`<img
                                src=${a}
                                alt=${r}
                                loading="lazy"
                                @error=${()=>this._failed=new Set([...this._failed,a])}
                              />`:E`<span class="placeholder">
                                <ha-icon icon="mdi:image-off-outline" aria-hidden="true"></ha-icon>
                                <span>${l(e,`cameras.no_image`)}</span>
                              </span>`}
                      </span>
                      <span class="name">${r}</span>
                    </button>
                  </div>`})}
              </div>`:F(`mdi:cctv-off`,l(e,`cameras.empty`))}
      </div>`}},It=[`moderate`,`high`,`extreme`,`catastrophic`],Lt={moderate:`green`,high:`yellow`,extreme:`orange`,catastrophic:`red`,no_rating:`grey`},Rt={moderate:`mdi:fire`,high:`mdi:fire`,extreme:`mdi:fire-alert`,catastrophic:`mdi:fire-alert`,no_rating:`mdi:fire-off`};function zt(e){if(typeof e!=`string`)return`no_rating`;let t=e.trim().toLowerCase();return t.includes(`catastrophic`)?`catastrophic`:t.includes(`extreme`)?`extreme`:t.includes(`high`)?`high`:t.includes(`moderate`)?`moderate`:`no_rating`}function Bt(e){return Lt[e]}var Vt={good:`green`,fair:`yellow`,poor:`orange`,very_poor:`red`,extremely_poor:`purple`,unknown:`grey`};function Ht(e){if(typeof e!=`string`)return`unknown`;let t=e.trim().toLowerCase();return t.includes(`extremely`)||t.includes(`hazardous`)?`extremely_poor`:t.includes(`very poor`)||t.includes(`very_poor`)?`very_poor`:t.includes(`poor`)?`poor`:t.includes(`fair`)||t.includes(`moderate`)?`fair`:t.includes(`good`)||t.includes(`very good`)?`good`:`unknown`}function Ut(e){return Vt[e]}function Wt(e){if(typeof e!=`string`)return`grey`;let t=e.toLowerCase();return t.includes(`closed`)||t.includes(`closure`)?`red`:t.includes(`flood`)?`blue`:t.includes(`hazard`)||t.includes(`caution`)||t.includes(`restrict`)||t.includes(`lane`)?`amber`:t.includes(`open`)?`green`:`grey`}function Gt(e){let t=Wt(e);return t===`red`?`mdi:road-variant`:t===`blue`?`mdi:waves`:t===`amber`?`mdi:traffic-cone`:`mdi:road`}var Kt=[`N`,`NNE`,`NE`,`ENE`,`E`,`ESE`,`SE`,`SSE`,`S`,`SSW`,`SW`,`WSW`,`W`,`WNW`,`NW`,`NNW`];function qt(e){return Kt[Math.round((e%360+360)%360/22.5)%16]}var Jt=[{attr:`pm2_5`,label:`PM2.5`},{attr:`pm10`,label:`PM10`},{attr:`no2`,label:`NO₂`},{attr:`o3`,label:`O₃`}],Yt=class extends H{static styles=[...H.styles,h`
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
    `];titleKey=`conditions.title`;entityKeys(){return[n.primaryWeatherObservation,n.airQualityRating]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 4}metric(e,t){return t===void 0||t===``?O:E`<div class="metric"><dt>${e}</dt><dd>${t}</dd></div>`}renderWeather(e,t){if(!t||J(t))return F(`mdi:weather-cloudy-alert`,l(e,`conditions.no_weather`));let n=t.attributes,r=(r,i)=>{let a=Z(n[r]);return a===void 0?void 0:`${Dt(e,t,r,a)} ${i}`},i=Z(n.wind_direction_deg),a=r(`wind_speed_avg_kph`,`km/h`),o=Z($(n.stations)[0]?.rain_since_9am),s=Q(n.station_name),c=a===void 0?void 0:E`${i===void 0?O:E`<ha-icon
                    icon="mdi:navigation"
                    style=${N({transform:`rotate(${i+180}deg)`})}
                    aria-hidden="true"
                  ></ha-icon>`}<span>${a}${i===void 0?``:` ${qt(i)}`}</span>${i===void 0?O:E`<span class="sr-only">${l(e,`conditions.wind_from`,{direction:qt(i)})}</span>`}`;return E`<button
        class="plain temperature"
        aria-label=${`${l(e,`conditions.temperature`)} ${Et(e,t)}. ${l(e,`action.details`)}`}
        @click=${()=>this.moreInfo(t.entity_id)}
      >
        <span class="value">${Et(e,t)}</span>
        ${s?E`<span class="secondary">${l(e,`conditions.station`,{name:s})}</span>`:O}
      </button>
      <dl class="metrics">
        ${this.metric(l(e,`conditions.feels_like`),r(`apparent_temperature`,`°C`))}
        ${this.metric(l(e,`conditions.humidity`),r(`relative_humidity`,`%`))}
        ${this.metric(l(e,`conditions.wind`),c)}
        ${this.metric(l(e,`conditions.gust`),r(`wind_speed_max_kph`,`km/h`))}
        ${this.metric(l(e,`conditions.pressure`),r(`pressure_hpa`,`hPa`))}
        ${this.metric(l(e,`conditions.rain`),o===void 0?void 0:`${Dt(e,t,`rain_since_9am`,o)} mm`)}
      </dl>`}renderAirQuality(e,t){if(!t||J(t))return F(`mdi:air-filter`,l(e,`conditions.no_air_quality`));let n=Q(t.attributes.station_name);return E`<dl class="metrics">
        ${Jt.map(n=>this.metric(n.label,Q(t.attributes[n.attr])??(Z(t.attributes[n.attr])===void 0?void 0:Dt(e,t,n.attr))))}
      </dl>
      ${n?E`<span class="secondary">${l(e,`conditions.station`,{name:n})}</span>`:O}`}renderBody(e,t){let r=V(e,this.deviceId,n.primaryWeatherObservation),i=V(e,this.deviceId,n.airQualityRating),a=Ht(J(i)?void 0:i?.state),o=J(i)?void 0:a===`unknown`?Q(i?.state):l(e,`conditions.aq.${a}`);return E`${L({title:this.cardTitle(),icon:`mdi:weather-partly-cloudy`})}
      <div class="content">
        <section class="group" aria-label=${l(e,`conditions.weather`)}>${this.renderWeather(e,r)}</section>
        <hr class="divider" />
        <section class="group" aria-label=${l(e,`conditions.air_quality`)}>
          <div class="group-head">
            <h3 class="group-title">${l(e,`conditions.air_quality`)}</h3>
            ${o?E`<button class="plain" aria-label=${`${l(e,`conditions.air_quality`)}: ${o}. ${l(e,`action.details`)}`} @click=${()=>this.moreInfo(i?.entity_id)}>
                    ${P(o,Ut(a),`mdi:air-filter`)}
                  </button>`:O}
          </div>
          ${this.renderAirQuality(e,i)}
        </section>
      </div>`}},Xt=class extends H{static styles=[...H.styles,h`
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
    `];titleKey=`fire.title`;entityKeys(){return[n.fireDangerRating]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getGridOptions(){return{columns:6,rows:`auto`,min_columns:6}}renderBody(e,t){let r=V(e,this.deviceId,n.fireDangerRating),i=L({title:this.cardTitle(),icon:`mdi:fire`,detailsLabel:l(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(!r||r.state===`unavailable`)return E`${i}<div class="content">
          ${I(`warning`,l(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let a=zt(J(r)?void 0:r.state),o=Bt(a),s=l(e,`fire.rating.${a}`),c=Q(r.attributes.district_name),u=Q(r.attributes.day),d=r.attributes.total_fire_ban===!0;return E`${i}
      <div class="content">
        <div class="rating">
          ${Xe(Rt[a],o,!0)}
          <div class="rating-text">
            <span class="rating-label">${s}</span>
            ${c||u?E`<span class="secondary"
                    >${[c?l(e,`fire.district`,{district:c}):void 0,u?l(e,`fire.forecast_for`,{day:u}):void 0].filter(Boolean).join(` · `)}</span
                  >`:O}
          </div>
        </div>
        <ol class="scale" aria-label=${l(e,`fire.scale`)}>
          ${It.map(t=>{let n=t===a,r=l(e,`fire.rating.${t}`);return E`<li
              class="segment ${n?`active`:``}"
              style=${N({"--tone":Je(Bt(t))})}
              aria-current=${n?`true`:O}
            >
              <span class="bar" aria-hidden="true"></span>
              <span class="name">${r}</span>
              ${n?E`<span class="sr-only">${l(e,`fire.current`)}</span>`:O}
            </li>`})}
        </ol>
        <div class="badges">
          ${d?P(l(e,`fire.total_fire_ban`),`red`,`mdi:fire-off`):P(l(e,`fire.no_total_fire_ban`),`grey`,`mdi:check`)}
        </div>
      </div>`}},Zt={emergency:{level:`emergency`,tone:`red`,icon:`mdi:alert-octagon`,rank:4},watch_and_act:{level:`watch_and_act`,tone:`orange`,icon:`mdi:alert`,rank:3},advice:{level:`advice`,tone:`amber`,icon:`mdi:information`,rank:2},information:{level:`information`,tone:`blue`,icon:`mdi:information-outline`,rank:1},unknown:{level:`unknown`,tone:`grey`,icon:`mdi:help-circle-outline`,rank:0}};function Qt(e){if(typeof e!=`string`)return`unknown`;let t=e.trim().toLowerCase();return t.includes(`emergency`)?`emergency`:t.includes(`watch and act`)||t.includes(`watch & act`)?`watch_and_act`:t.includes(`advice`)?`advice`:t.includes(`info`)||t.includes(`routine`)||t.includes(`notification`)?`information`:`unknown`}function $t(e){return Zt[Qt(e)]}function en(e,t){return e===void 0||e===`unavailable`||e===`unknown`?`unavailable`:e.trim().toLowerCase()===`all clear`?t===void 0||t>0?`unknown`:`all_clear`:Qt(e)}function tn(e){return e===`all_clear`?{level:`unknown`,tone:`green`,icon:`mdi:shield-check`,rank:0}:e===`unavailable`?{level:`unknown`,tone:`grey`,icon:`mdi:cloud-off-outline`,rank:-1}:Zt[e]}var nn=[`fire`,`flood_storm`,`geological`,`roads`,`other`],rn={Bushfire:{category:`fire`,icon:`mdi:fire`},"Grass Fire":{category:`fire`,icon:`mdi:grass`},"Structure Fire":{category:`fire`,icon:`mdi:fire-alert`},Flood:{category:`flood_storm`,icon:`mdi:water-alert`},"Severe Storm":{category:`flood_storm`,icon:`mdi:weather-lightning`},"Tropical Cyclone":{category:`flood_storm`,icon:`mdi:weather-hurricane`},Earthquake:{category:`geological`,icon:`mdi:pulse`},Volcano:{category:`geological`,icon:`mdi:volcano`},Tsunami:{category:`geological`,icon:`mdi:tsunami`},"Road Hazard / Crash":{category:`roads`,icon:`mdi:car-emergency`},"Hazmat Incident":{category:`other`,icon:`mdi:biohazard`},Other:{category:`other`,icon:`mdi:alert-decagram`}},an={fire:`mdi:fire`,flood_storm:`mdi:weather-pouring`,geological:`mdi:earth`,roads:`mdi:car-emergency`,other:`mdi:alert-decagram`};function on(e){return typeof e==`string`&&rn[e]?.category||`other`}function sn(e){return typeof e==`string`&&rn[e]?.icon||`mdi:alert-decagram`}var cn=10,ln={emergency:`status.level.emergency`,watch_and_act:`status.level.watch_and_act`,advice:`status.level.advice`,information:`status.level.information`,unknown:`status.level.unknown`},un=class extends H{static properties={...H.properties,_category:{state:!0},_showBurns:{state:!0},_expanded:{state:!0}};titleKey=`incidents.title`;usesIncidents=!0;constructor(){super(),this._category=`all`,this._showBurns=void 0,this._expanded=!1}static validateConfig(e){super.validateConfig(e);let t=e;q(t,`max_items`,1,100),yt(t,`show_planned_burns`),bt(t,`categories`,nn)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}},{name:`show_planned_burns`,selector:{boolean:{}}},{name:`categories`,selector:{select:{multiple:!0,mode:`list`,options:nn.map(e=>({value:e,label:l(void 0,`incidents.category.${e}`)}))}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 2+Math.min(this._config?.max_items??cn,6)}get showBurns(){return this._showBurns??this._config?.show_planned_burns??!1}categories(){let e=this._config?.categories;return e?.length?e:nn}renderIncident(e,t){let n=t.attributes,r=$t(n.warning_level),i=ct(t),a=At(e,n.updated_at),o=[Q(n.location_name),X(e,lt(t)),a?l(e,`incidents.updated`,{time:a}):void 0].filter(Boolean).join(` · `);return R({icon:Q(n.icon)??sn(n.hazard_type),tone:r.tone,headline:i,supporting:E`${n.is_hazard_reduction?E`${l(e,`incidents.planned_burn`)} · `:O}${o}`,badge:P(l(e,ln[r.level]),r.tone,r.icon),onActivate:()=>this.moreInfo(t.entity_id),link:Mt(n.web_url),linkLabel:`${l(e,`action.open_link`)}: ${i}`})}renderBody(e,t){let n=this.categories(),r=st(e,this.entryId).filter(e=>n.includes(on(e.attributes.hazard_type))),i=r.some(e=>e.attributes.is_hazard_reduction===!0),a=this.showBurns?r:r.filter(e=>e.attributes.is_hazard_reduction!==!0),o=new Map;for(let e of a){let t=on(e.attributes.hazard_type);o.set(t,(o.get(t)??0)+1)}let s=this._category!==`all`&&n.includes(this._category)?this._category:`all`,c=s===`all`?a:a.filter(e=>on(e.attributes.hazard_type)===s),u=t.max_items??cn,d=this._expanded?c:c.slice(0,u),f=(t,n)=>E`<ha-filter-chip
      .selected=${s===t}
      .label=${`${l(e,`incidents.category.${t}`)} ${n}`}
      @click=${e=>{e.preventDefault(),this._category=t,this._expanded=!1}}
    >
      ${t===`all`?O:E`<ha-icon slot="icon" .icon=${an[t]}></ha-icon>`}
    </ha-filter-chip>`;return E`${L({title:this.cardTitle(),icon:`mdi:alert-decagram`,count:String(a.length)})}
      <div class="content">
        ${r.length?E`<ha-chip-set aria-label=${l(e,`incidents.filters`)}>
                ${f(`all`,a.length)}
                ${n.length>1?n.map(e=>f(e,o.get(e)??0)):O}
                ${i?E`<ha-filter-chip
                        .selected=${this.showBurns}
                        .label=${l(e,`incidents.planned_burns`)}
                        @click=${e=>{e.preventDefault(),this._showBurns=!this.showBurns}}
                      >
                        <ha-icon slot="icon" icon="mdi:fire-circle"></ha-icon>
                      </ha-filter-chip>`:O}
              </ha-chip-set>`:O}
        ${d.length?z(d.map(t=>this.renderIncident(e,t)),this.cardTitle()):F(`mdi:shield-check-outline`,l(e,r.length?`incidents.empty_filtered`:`incidents.empty`))}
        ${c.length>u?Ze(e,this._expanded,c.length,()=>this._expanded=!this._expanded):O}
      </div>`}},dn=(function(){let e=typeof document<`u`&&document.createElement(`link`).relList;return e&&e.supports&&e.supports(`modulepreload`)?`modulepreload`:`preload`})(),fn=function(e,t){return new URL(e,t).href},pn={},mn=function(e){return e.pathname.endsWith(`.css`)},hn=function(e,t,n){if(t in e)return e[t];let r=n();if(!r){e[t]=void 0;return}let i=r.then(()=>{e[t]=void 0},n=>{throw e[t]=void 0,n});return e[t]=i,i},gn=function(e,t,n){let r=Promise.resolve();if(t&&t.length>0){let e,i=document.querySelector(`meta[property=csp-nonce]`),a=i?.nonce||i?.getAttribute(`nonce`);function o(e){return Promise.all(e.map(e=>Promise.resolve(e).then(e=>({status:`fulfilled`,value:e}),e=>({status:`rejected`,reason:e}))))}function s(e){return import.meta.resolve?new URL(import.meta.resolve(e)):new URL(e,import.meta.url)}r=o(t.map(t=>{t=fn(t,n);let r=s(t),i=mn(r);return hn(pn,r.href,()=>{if(e===void 0){e={all:new Set,styles:new Set};let t=document.getElementsByTagName(`link`);for(let n=t.length-1;n>=0;n--){let r=t[n];e.all.add(r.href),r.rel===`stylesheet`&&e.styles.add(r.href)}}if((i?e.styles:e.all).has(r.href))return;let t=document.createElement(`link`);if(t.rel=i?`stylesheet`:dn,i||(t.as=`script`),t.crossOrigin=``,t.href=r.href,a&&t.setAttribute(`nonce`,a),document.head.appendChild(t),i)return new Promise((e,n)=>{t.addEventListener(`load`,e),t.addEventListener(`error`,()=>n(Error(`Unable to preload CSS for ${r}`)))})})}).filter(e=>e!==void 0))}function i(e){let t=new Event(`vite:preloadError`,{cancelable:!0});if(t.payload=e,window.dispatchEvent(t),!t.defaultPrevented)throw e}return r.then(t=>{for(let e of t||[])e.status===`rejected`&&i(e.reason);return e().catch(i)})},_n=.7,vn,yn=()=>vn??=gn(()=>import(`./ausnz-disaster-leaflet-map-DjAmBMBR.js`),[],import.meta.url),bn=class extends H{static properties={...H.properties,_radar:{state:!0},_loadError:{state:!0}};static styles=[...H.styles,h`
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
    `];titleKey=`map.title`;usesIncidents=!0;_map;_container;_creating=!1;_resizeObserver;_intersectionObserver;_reducedMotion=typeof matchMedia==`function`&&matchMedia(`(prefers-reduced-motion: reduce)`).matches;constructor(){super(),this._radar={state:`off`},this._loadError=!1}static validateConfig(e){super.validateConfig(e);let t=e;q(t,`zoom`,1,18),yt(t,`radar`),vt(t,`radar_opacity`,.1,1)}static getConfigForm(){return{schema:[...W(),{name:`zoom`,selector:{number:{min:1,max:18,mode:`box`}}},{name:`radar`,default:!0,selector:{boolean:{}}},{name:`radar_opacity`,selector:{number:{min:.1,max:1,step:.05,mode:`slider`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getGridOptions(){return{columns:12,rows:6,min_columns:6,min_rows:4}}getCardSize(){return 7}trackedHomeId=`zone.home`;trackedEntityIds(e){return[...super.trackedEntityIds(e),this.trackedHomeId]}connectedCallback(){super.connectedCallback(),this.hasUpdated&&this.ensureMap()}disconnectedCallback(){super.disconnectedCallback(),this.teardown()}teardown(){this._resizeObserver?.disconnect(),this._intersectionObserver?.disconnect(),this._resizeObserver=void 0,this._intersectionObserver=void 0,this._map?.destroy(),this._map=void 0,this._container=void 0}updated(e){super.updated(e),this._map&&this.renderRoot.querySelector(`.map`)!==this._container&&this.teardown(),this._map?(e.has(`hass`)||e.has(`_config`))&&this._map.update(this.viewOptions()):this.ensureMap()}viewOptions(){let e=this.hass,t=st(e,this.entryId).flatMap(t=>{let n=Z(t.attributes.latitude),r=Z(t.attributes.longitude);if(n===void 0||r===void 0)return[];let i=$t(t.attributes.warning_level);return[{id:t.entity_id,title:ct(t),levelLabel:l(e,ln[i.level]),tone:i.tone,latitude:n,longitude:r,agency:Q(t.attributes.responsible_agency)??Q(t.attributes.agency)}]}),n=e.states[this.trackedHomeId],r=Z(n?.attributes.latitude),i=Z(n?.attributes.longitude);return{incidents:t,home:r!==void 0&&i!==void 0?{latitude:r,longitude:i,radius:Z(n?.attributes.radius),label:l(e,`map.home`)}:Number.isFinite(e.config?.latitude)&&Number.isFinite(e.config?.longitude)?{latitude:e.config.latitude,longitude:e.config.longitude,label:l(e,`map.home`)}:void 0,darkMode:!!e.themes?.darkMode,zoom:this._config?.zoom,radar:this._config?.radar!==!1,radarOpacity:this._config?.radar_opacity??_n}}async ensureMap(){if(this._map||this._creating||!this.hass||!this.isConnected)return;let e=this.renderRoot.querySelector(`.map`);if(e){this._creating=!0;try{let t=await yn(),n=this.renderRoot;if(!n.adoptedStyleSheets.some(e=>e.leaflet)){let e=new CSSStyleSheet;e.replaceSync(t.leafletCss),e.leaflet=!0,n.adoptedStyleSheets=[e,...n.adoptedStyleSheets]}if(!this.isConnected||this._map||!e.isConnected)return;this._container=e,this._map=new t.IncidentMap(e,this.hass.connection,e=>this._radar=e,e=>this.moreInfo(e),this._reducedMotion),this._resizeObserver=new ResizeObserver(()=>this._map?.invalidateSize()),this._resizeObserver.observe(e),this._intersectionObserver=new IntersectionObserver(e=>this._map?.setVisible(e.some(e=>e.isIntersecting))),this._intersectionObserver.observe(this),this._map.update(this.viewOptions())}catch(e){console.error(`Disaster Watch map failed to load`,e),this._loadError=!0}finally{this._creating=!1}}}togglePlay(){let e=!this._radar.playing;this._map?.setPlaying(e)}renderRadarBar(e){let t=this._radar;if(t.state!==`ok`||t.frameTime===void 0)return O;let n=jt(e,t.frameTime,{timeStyle:`short`}),r=At(e,t.frameTime),i=!!t.playing;return E`<div class="radar-bar">
      <ha-icon-button .label=${l(e,i?`map.pause`:`map.play`)} aria-pressed=${i?`true`:`false`} @click=${this.togglePlay}>
        <ha-icon .icon=${i?`mdi:pause`:`mdi:play`}></ha-icon>
      </ha-icon-button>
      <span class="time" aria-live=${i?`off`:`polite`}>${l(e,`map.radar_at`,{time:n??``})}${r?` · ${r}`:``}</span>
      <span class="frames" aria-hidden="true">
        ${Array.from({length:t.frameCount??0},(e,n)=>E`<span class=${n===t.frameIndex?`current`:``}></span>`)}
      </span>
    </div>`}renderBody(e,t){let n=rt(e,this.deviceId)??e.config?.location_name??``;return E`${L({title:this.cardTitle(),icon:`mdi:map-marker-radius`})}
      <div class="map-wrap">
        <div class="map" role="region" aria-label=${l(e,`map.label`,{name:n})}></div>
      </div>
      ${this.renderRadarBar(e)}
      ${this._radar.state===`unavailable`?E`<div class="notice">${I(`info`,l(e,`map.radar_unavailable`))}</div>`:O}
      ${this._loadError?E`<div class="notice">${I(`error`,l(e,`state.unavailable`))}</div>`:O}`}};function xn(e,t){return(J(e)?void 0:Z(e?.state))??Z(t)}var Sn=8,Cn=class extends H{static properties={...H.properties,_expanded:{state:!0}};titleKey=`outages.title`;constructor(){super(),this._expanded=!1}entityKeys(){return[n.powerOutagesCount,n.powerOutagesCustomersAffected]}static validateConfig(e){super.validateConfig(e),q(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}renderBody(e,t){let r=V(e,this.deviceId,n.powerOutagesCount),i=L({title:this.cardTitle(),icon:`mdi:transmission-tower-off`,detailsLabel:l(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(J(r))return E`${i}<div class="content">
          ${I(`warning`,l(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let a=$(r.attributes.outages),o=Z(r.state)??a.length,s=xn(V(e,this.deviceId,n.powerOutagesCustomersAffected),r.attributes.customers_affected),c=t.max_items??Sn,u=this._expanded?a:a.slice(0,c);return E`${i}
      <div class="content">
        ${o===0?F(`mdi:transmission-tower`,l(e,`outages.empty`)):E`<span class="secondary"
                  >${s===void 0?l(e,`outages.summary_count`,{count:Y(e,o)}):l(e,`outages.summary`,{count:Y(e,o),customers:Y(e,s)})}</span
                >
                ${z(u.map(t=>{let n=jt(e,t.restore_time,{weekday:`short`,hour:`numeric`,minute:`2-digit`})??Q(t.restore_time),r=Z(t.customers_affected);return R({icon:`mdi:transmission-tower-off`,tone:`amber`,headline:Q(t.suburb)??`—`,supporting:[Q(t.cause),n?l(e,`outages.restore`,{time:n}):void 0].filter(Boolean).join(` · `)||void 0,trailing:r===void 0?void 0:E`<span class="secondary"
                              >${l(e,`outages.customers`,{count:Y(e,r)})}</span
                            >`})}),this.cardTitle())}
                ${a.length>c?Ze(e,this._expanded,a.length,()=>this._expanded=!this._expanded):O}`}
      </div>`}},wn=[{key:`evacuation_centre`,icon:`mdi:home-group`},{key:`place_of_refuge`,icon:`mdi:home-heart`},{key:`sandbag_station`,icon:`mdi:sack`},{key:`other`,icon:`mdi:home-alert`}];function Tn(e){return e===`evacuation_centre`||e===`place_of_refuge`||e===`sandbag_station`?e:`other`}var En=class extends H{titleKey=`relief.title`;entityKeys(){return[n.reliefFacilitiesCount,n.highestWarningLevel,n.weatherWarningsCount]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 5}renderBody(e,t){let r=V(e,this.deviceId,n.reliefFacilitiesCount),i=V(e,this.deviceId,n.highestWarningLevel),a=V(e,this.deviceId,n.weatherWarningsCount),o=L({title:this.cardTitle(),icon:`mdi:home-heart`,detailsLabel:l(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(J(r))return E`${o}<div class="content">
          ${I(`warning`,l(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let s=$(r.attributes.facilities).sort((e,t)=>(Z(e.distance_km)??1/0)-(Z(t.distance_km)??1/0)),c=$(i?.attributes.nearby_councils??a?.attributes.nearby_councils).filter(e=>Q(e.name)||Q(e.url));return E`${o}
      <div class="content">
        ${s.length===0?F(`mdi:home-search-outline`,l(e,`relief.empty`)):O}
        ${wn.map(({key:t,icon:n})=>{let r=s.filter(e=>Tn(e.facility_type)===t);if(!r.length)return O;let i=l(e,`relief.group.${t}`);return E`<h3 class="list-title">${i}</h3>
            ${z(r.map(t=>{let r=(Q(t.status)??`Open`).toLowerCase()!==`closed`,a=Q(t.name)??i;return R({icon:n,tone:r?`green`:`grey`,headline:a,supporting:Q(t.address)??Q(t.suburb),badge:P(l(e,r?`relief.open`:`relief.closed`),r?`green`:`grey`,r?`mdi:door-open`:`mdi:door-closed`),trailing:X(e,Z(t.distance_km))})}),i)}`})}
        ${c.length?E`<h3 class="list-title">${l(e,`relief.councils`)}</h3>
                ${z(c.map(t=>{let n=Q(t.name)??Q(t.url)??``,r=Mt(t.url);return R({icon:`mdi:view-dashboard-outline`,tone:`blue`,headline:n,supporting:r?new URL(r).hostname:void 0,link:r,linkLabel:`${l(e,`action.open_link`)}: ${n}`})}),l(e,`relief.councils`))}`:O}
      </div>`}},Dn=8,On=class extends H{static properties={...H.properties,_expanded:{state:!0}};titleKey=`roads.title`;constructor(){super(),this._expanded=!1}entityKeys(){return[n.roadClosuresCount]}static validateConfig(e){super.validateConfig(e),q(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}renderBody(e,t){let r=V(e,this.deviceId,n.roadClosuresCount),i=J(r),a=i?[]:$(r.attributes.closures),o=i?void 0:Z(r.state)??a.length,s=L({title:this.cardTitle(),icon:`mdi:traffic-cone`,count:o?String(o):void 0,detailsLabel:l(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0});if(i)return E`${s}<div class="content">
          ${I(`warning`,l(e,r?`state.unavailable`:`state.entity_missing`))}
        </div>`;let c=[...a].sort((e,t)=>(Z(e.distance_km)??1/0)-(Z(t.distance_km)??1/0)),u=t.max_items??Dn,d=this._expanded?c:c.slice(0,u);return E`${s}
      <div class="content">
        ${c.length?z(d.map(t=>{let n=Q(t.status)??`—`,r=Wt(n),i=At(e,t.updated_at);return R({icon:Gt(n),tone:r,headline:[Q(t.road),Q(t.suburb)].filter(Boolean).join(`, `)||n,supporting:[Q(t.advice)??Q(t.description)??Q(t.reason),i].filter(Boolean).join(` · `)||void 0,badge:P(n,r),trailing:X(e,Z(t.distance_km))})}),this.cardTitle()):F(`mdi:road-variant`,l(e,`roads.empty`))}
        ${c.length>u?Ze(e,this._expanded,c.length,()=>this._expanded=!this._expanded):O}
      </div>`}},kn=[{key:n.emergencyWarningNearby,icon:`mdi:alert-octagon`,label:`status.chip.emergency_warning_nearby`},{key:n.activeHazardsNearby,icon:`mdi:alert`,label:`status.chip.active_hazards_nearby`},{key:n.powerOutageActive,icon:`mdi:transmission-tower-off`,label:`status.chip.power_outage_active`},{key:n.roadClosureNearby,icon:`mdi:traffic-cone`,label:`status.chip.road_closure_nearby`}],An={all_clear:`status.all_clear`,unavailable:`status.unavailable`,emergency:`status.level.emergency`,watch_and_act:`status.level.watch_and_act`,advice:`status.level.advice`,information:`status.level.information`,unknown:`status.level.unknown`},jn=class extends H{static styles=[...H.styles,h`
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
    `];titleKey=`card.status.name`;entityKeys(){return[n.highestWarningLevel,n.activeHazardsCount,n.nearestHazardDistance,n.nearestHazardTitle,...kn.map(e=>e.key)]}static getConfigForm(){return{schema:W(),computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getGridOptions(){return{columns:12,rows:`auto`,min_columns:6}}getCardSize(){return 2}renderBody(e,t){let r=this.deviceId,i=V(e,r,n.highestWarningLevel),a=V(e,r,n.activeHazardsCount),o=J(a)?void 0:Z(a?.state),s=en(J(i)?void 0:i?.state,o),c=tn(s),u=l(e,An[s]),d=V(e,r,n.nearestHazardDistance),f=V(e,r,n.nearestHazardTitle),ee=J(d)?void 0:Z(d?.state),p=Q(d?.attributes.title)??(J(f)||f?.state===`None`?void 0:Q(f?.state)),m=``;s!==`unavailable`&&o!==void 0&&(m=o===0?l(e,`status.no_hazards`):o===1?l(e,`status.hazard`):l(e,`status.hazards`,{count:o}));let h=X(e,ee),g=o&&h?`${l(e,`status.nearest`,{distance:h})}${p?` — ${p}`:``}`:void 0,te=kn.map(t=>({...t,stateObj:V(e,r,t.key)})).filter(e=>e.stateObj?.state===`on`);return E`<div class="content status">
      <button
        class="plain hero"
        aria-label=${`${u}. ${m}${g?`, ${g}`:``}. ${l(e,`action.details`)}`}
        @click=${()=>this.moreInfo(i?.entity_id)}
      >
        <span class="bubble large" style=${N({"--tone":Je(c.tone)})} aria-hidden="true">
          <ha-icon .icon=${c.icon}></ha-icon>
        </span>
        <span class="hero-text">
          <span class="level">${u}</span>
          ${m?E`<span class="summary">${m}</span>`:O}
          ${g?E`<span class="summary nearest">${g}</span>`:O}
        </span>
      </button>
      ${te.length?E`<ha-chip-set aria-label=${l(e,`status.alerts`)}>
              ${te.map(t=>E`<ha-assist-chip
                  filled
                  .label=${l(e,t.label)}
                  @click=${()=>this.moreInfo(t.stateObj?.entity_id)}
                >
                  <ha-icon slot="icon" .icon=${t.icon}></ha-icon>
                </ha-assist-chip>`)}
            </ha-chip-set>`:O}
    </div>`}},Mn=8,Nn={status:jn,incidents:un,warnings:class extends H{static properties={...H.properties,_view:{state:!0},_expanded:{state:!0}};titleKey=`warnings.title`;constructor(){super(),this._view=`warnings`,this._expanded=!1}entityKeys(){return[n.weatherWarningsCount,n.highestWarningLevel]}static validateConfig(e){super.validateConfig(e),q(e,`max_items`,1,100)}static getConfigForm(){return{schema:[...W(),{name:`max_items`,selector:{number:{min:1,max:100,mode:`box`}}}],computeLabel:G,computeHelper:K,assertConfig:e=>this.validateConfig(e)}}static getStubConfig(e){return U(e)}getCardSize(){return 5}renderItem(e,t,n){let r=Q(t.title)??``,i=At(e,t.pub_date),a=Q(t.locations)??Q(t.description);return R({icon:n,tone:this._view===`warnings`?`orange`:`blue`,headline:r,supporting:[a,i].filter(Boolean).join(` · `)||void 0,link:Mt(t.link),linkLabel:`${l(e,`action.open_link`)}: ${r}`})}renderBody(e,t){let r=V(e,this.deviceId,n.weatherWarningsCount),i=V(e,this.deviceId,n.highestWarningLevel),a=J(r),o=$(r?.attributes.warnings),s=$(r?.attributes.emergency_news??i?.attributes.emergency_news),c=a?0:Z(r?.state)??o.length,u=this._view===`warnings`?o:s,d=t.max_items??Mn,f=this._expanded?u:u.slice(0,d),ee=this._view===`warnings`?`mdi:weather-lightning-rainy`:`mdi:newspaper-variant-outline`,p=(e,t)=>E`<ha-filter-chip
      no-leading-icon
      .selected=${this._view===e}
      .label=${t}
      @click=${t=>{t.preventDefault(),this._view=e,this._expanded=!1}}
    ></ha-filter-chip>`;return E`${L({title:this.cardTitle(),icon:`mdi:weather-lightning-rainy`,detailsLabel:l(e,`action.details`),onDetails:r?()=>this.moreInfo(r.entity_id):void 0})}
      <div class="content">
        ${a?I(`warning`,l(e,r?`state.unavailable`:`state.entity_missing`)):E`<ha-chip-set aria-label=${l(e,`warnings.views`)}>
                  ${p(`warnings`,l(e,`warnings.tab.warnings`,{count:c}))}
                  ${p(`news`,l(e,`warnings.tab.news`,{count:s.length}))}
                </ha-chip-set>
                ${f.length?z(f.map(t=>this.renderItem(e,t,ee))):F(`mdi:check-circle-outline`,l(e,this._view===`warnings`?`warnings.empty`:`warnings.news_empty`))}
                ${u.length>d?Ze(e,this._expanded,u.length,()=>this._expanded=!this._expanded):O}
`}
      </div>`}},fire_danger:Xt,outages:Cn,roads:On,conditions:Yt,relief:En,cameras:Ft,map:bn},Pn=[{tag:i,ctor:St,key:`all`},...Object.keys(Nn).map(e=>({tag:r[e],ctor:Nn[e],key:e}))];window.customCards=window.customCards||[];for(let{tag:e,ctor:n,key:r}of Pn)customElements.get(e)||customElements.define(e,n),window.customCards.some(t=>t.type===e)||window.customCards.push({type:e,name:l(void 0,`card.${r}.name`),description:l(void 0,`card.${r}.description`),preview:!0,documentationURL:t});
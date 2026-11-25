// Plain SVG/CSS status chart. Owner: Dastan
import { Component, input } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';

@Component({selector:'app-status-donut',standalone:true,imports:[TranslatePipe],template:`<h3 class="h6">{{'admin.chart_status'|translate}}</h3><div class="d-flex flex-wrap gap-2">@for(r of rows(); track r.status){<div><span class="badge me-1" [style.background]="color(r.status)">{{r.status}}</span><strong>{{r.count}}</strong></div>}</div>`})
export class StatusDonutComponent { rows=input<{status:string;count:number}[]>([]); color(s:string){return s==='Expired'?'#6c757d':s==='Cancelled'?'#dc3545':s==='Confirmed'?'#198754':s==='Completed'?'#0d6efd':'#ffc107';} }

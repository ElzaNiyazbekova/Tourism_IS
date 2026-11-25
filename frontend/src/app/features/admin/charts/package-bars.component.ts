// Plain CSS horizontal revenue bars. Owner: Dastan
import { Component, input } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';

@Component({selector:'app-package-bars',standalone:true,imports:[TranslatePipe],template:`<h3 class="h6">{{'admin.chart_packages'|translate}}</h3>@for(r of rows(); track r.package_id){<div class="mb-2"><div class="d-flex justify-content-between small"><span>{{r.title}}</span><span>{{r.revenue}}</span></div><div class="bg-light rounded"><div class="rounded" [style.width.%]="width(r.revenue)" style="height:10px;background:#5f72c7"></div></div></div>}`})
export class PackageBarsComponent { rows=input<{package_id:number;title:string;revenue:string}[]>([]); width(v:string){const n=Number(v); const max=Math.max(1,...this.rows().map(r=>Number(r.revenue))); return Math.max(2,n/max*100);} }

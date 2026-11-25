// Plain SVG monthly booking bars. Owner: Aitore
import { Component, input } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';

@Component({selector:'app-monthly-bars',standalone:true,imports:[TranslatePipe],template:`<h3 class="h6">{{'admin.chart_monthly'|translate}}</h3><svg viewBox="0 0 600 220" class="w-100" role="img"><g fill="#5f72c7">@for(r of rows(); track r.month; let i=$index){<rect [attr.x]="i*50+20" [attr.y]="200-barHeight(r.count)" width="34" [attr.height]="barHeight(r.count)"/><text [attr.x]="i*50+37" y="215" text-anchor="middle" font-size="10">{{r.month.slice(5)}}</text>}</g></svg>`})
export class MonthlyBarsComponent { rows=input<{month:string;count:number}[]>([]); barHeight(n:number){return Math.max(4, n*Math.max(4, this.max()/10));} private max(){return Math.max(1,...this.rows().map(r=>r.count));} }

// Admin dashboard: KPIs and plain-SVG/CSS charts. Owner: Aitore / Dastan
import { Component, inject, signal } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';
import { AdminService } from '../../core/api.services';
import { AdminStats } from '../../core/models';
import { MonthlyBarsComponent } from './charts/monthly-bars.component';
import { StatusDonutComponent } from './charts/status-donut.component';
import { PackageBarsComponent } from './charts/package-bars.component';

@Component({selector:'app-admin-dashboard',imports:[TranslatePipe,MonthlyBarsComponent,StatusDonutComponent,PackageBarsComponent],template:`
<h1 class="h4">{{'admin.dashboard'|translate}}</h1>
<div class="d-flex gap-2 mb-3"><input type="date" class="form-control" [value]="dateFrom()" (change)="dateFrom.set($any($event.target).value);load()"><input type="date" class="form-control" [value]="dateTo()" (change)="dateTo.set($any($event.target).value);load()"></div>
@if(loading()){<div class="text-center py-5"><div class="spinner-border"></div></div>}@else if(failed()){<div class="alert alert-danger">{{'common.load_failed'|translate}}</div>}@else if(stats(); as s){
<div class="row g-3 mb-3"><div class="col-md-3"><div class="card p-3"><small>{{'admin.kpi_bookings'|translate}}</small><div class="h4">{{s.totals.bookings}}</div></div></div><div class="col-md-3"><div class="card p-3"><small>{{'admin.kpi_revenue'|translate}}</small><div class="h4">{{s.totals.revenue}}</div></div></div><div class="col-md-3"><div class="card p-3"><small>{{'admin.kpi_average'|translate}}</small><div class="h4">{{s.totals.average_booking_value}}</div></div></div><div class="col-md-3"><div class="card p-3"><small>{{'admin.kpi_cancel_exp'|translate}}</small><div class="h4">{{(s.totals.cancellation_expiry_rate*100).toFixed(1)}}%</div></div></div></div>
<div class="row g-3"><div class="col-md-6 card p-3"><app-monthly-bars [rows]="s.bookings_per_month"/></div><div class="col-md-6 card p-3"><app-status-donut [rows]="s.bookings_by_status"/></div><div class="col-12 card p-3"><app-package-bars [rows]="s.top_packages_by_revenue"/></div></div>
}@else{<p class="text-muted">{{'common.empty'|translate}}</p>}`})
export class AdminDashboardComponent { private api=inject(AdminService); stats=signal<AdminStats|null>(null); loading=signal(true); failed=signal(false); dateFrom=signal(''); dateTo=signal(''); constructor(){this.load()} load(){this.loading.set(true);this.api.adminStats({date_from:this.dateFrom(),date_to:this.dateTo()}).subscribe({next:v=>{this.stats.set(v);this.loading.set(false)},error:()=>{this.failed.set(true);this.loading.set(false)}})} }

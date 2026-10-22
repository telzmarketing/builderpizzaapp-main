from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.exceptions import DomainError
from backend.core.response import err
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.schemas.preparation import RecipeIn, RecipeOut, PreparationOrderIn, PreparationOrderOut, PreparationCommandIn, PreparationReportIn
from backend.services.preparation_service import PreparationService

router=APIRouter(prefix="/preparation",tags=["preparation"])
view=require_rbac_permission("inventory","view"); manage=require_rbac_permission("inventory","manage")
def call(fn,*a):
    try:return fn(*a)
    except DomainError as e:return err(e)
def svc(db,a):return PreparationService(db,a.tenant_id,a.user_id)

@router.post("/recipes",status_code=201,response_model=RecipeOut)
def create_recipe(body:RecipeIn,db:Session=Depends(get_db),actor:AuthorizedTenantActor=Depends(manage)):return call(svc(db,actor).create_recipe,body)
@router.post("/orders",status_code=201,response_model=PreparationOrderOut)
def create_order(body:PreparationOrderIn,db:Session=Depends(get_db),actor:AuthorizedTenantActor=Depends(manage),key:str=Header(alias="Idempotency-Key",min_length=1,max_length=200)):return call(svc(db,actor).create_order,body,key)
@router.get("/orders")
def list_orders(status:str|None=Query(None),db:Session=Depends(get_db),actor:AuthorizedTenantActor=Depends(view)):return call(svc(db,actor).list_orders,status)
@router.post("/orders/{order_id}/{command}",response_model=PreparationOrderOut)
def command(order_id:str,command:str,body:PreparationCommandIn,db:Session=Depends(get_db),actor:AuthorizedTenantActor=Depends(manage),key:str=Header(alias="Idempotency-Key",min_length=1,max_length=200)):return call(svc(db,actor).command,order_id,command,body,key)
@router.post("/orders/{order_id}/reports",response_model=PreparationOrderOut)
def report(order_id:str,body:PreparationReportIn,db:Session=Depends(get_db),actor:AuthorizedTenantActor=Depends(manage),key:str=Header(alias="Idempotency-Key",min_length=1,max_length=200)):return call(svc(db,actor).report,order_id,body,key)
@router.post("/orders/{order_id}/complete",response_model=PreparationOrderOut)
def complete(order_id:str,body:PreparationCommandIn,db:Session=Depends(get_db),actor:AuthorizedTenantActor=Depends(manage),key:str=Header(alias="Idempotency-Key",min_length=1,max_length=200)):return call(svc(db,actor).complete,order_id,body,key)

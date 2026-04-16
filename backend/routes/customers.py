import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.customer import Customer, Address
from backend.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerOut,
    AddressCreate, AddressOut,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).order_by(Customer.name).all()


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    return customer


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    existing = db.query(Customer).filter(Customer.email == body.email).first()
    if existing:
        raise HTTPException(400, "E-mail já cadastrado.")
    customer = Customer(id=str(uuid.uuid4()), **body.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: str, body: CustomerUpdate, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


# ── Addresses ─────────────────────────────────────────────────────────────────

@router.get("/{customer_id}/addresses", response_model=list[AddressOut])
def list_addresses(customer_id: str, db: Session = Depends(get_db)):
    return db.query(Address).filter(Address.customer_id == customer_id).all()


@router.post("/{customer_id}/addresses", response_model=AddressOut, status_code=201)
def add_address(customer_id: str, body: AddressCreate, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    if body.is_default:
        db.query(Address).filter(Address.customer_id == customer_id).update({"is_default": False})
    address = Address(id=str(uuid.uuid4()), customer_id=customer_id, **body.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.delete("/{customer_id}/addresses/{address_id}", status_code=204)
def delete_address(customer_id: str, address_id: str, db: Session = Depends(get_db)):
    address = db.query(Address).filter(
        Address.id == address_id, Address.customer_id == customer_id
    ).first()
    if not address:
        raise HTTPException(404, "Endereço não encontrado.")
    db.delete(address)
    db.commit()

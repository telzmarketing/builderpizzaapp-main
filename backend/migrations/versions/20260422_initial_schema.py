"""Historical schema baseline immediately before the Payment Brick rollout.

Revision ID: 20260422_initial_schema
Revises: None

The compressed payload is the PostgreSQL DDL compiled from the authoritative
SQLAlchemy metadata at Git revision b5e33c3^.
"""
from __future__ import annotations

import base64
import gzip
import json
import re

from alembic import op

revision = "20260422_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA_B85 = """ABzY8`~hfc0{`tC+j88t^;dTMVtK|7xzwHMqvC85O>HTa<TPpB!C*=3E-I3sL2#w@*XJAnBmoe-tafE3ojz$r9Nf+g=LY=y#oO!U`R#IX``gdUMJaj0i;b)^wm838EH6L2U!1+nMWqOPC|ObQ9eeqD@sjSCq#OOSl%f<;aZ%9h<*OI3z43%hnXD95b>)l)1Enwv_P(cF!B0}sea;G{2c$eT1GAD!3nv*(_hc<3DS2{Nm-tN-L~R+lr+fS_Wf?3^GTk?!MZ&Vo{3F@AE>id%uFg)HGqn||yFUJ)2Z6!3A_<kLnPBDom(XfEG~n2Vo87G`pIRP;O{;zBQX=6>Z?<53vt0?f6+(~knU@6cwT6X<qf}d7mX@Z$XaH`OP%=qU4$B6t>BULL2wjO?L*ZNu5I7NaDT-iR7%l-cSOzh(gdJC`faR*Nrxa<OXf}ZLz~F`@U_FYFjiicK_&@TZ<P2BaThKnqSdRcSQI>O)OjMEO0PdKSG#evbBJvV&7;;!Rl#;ZlaKav57?njs^OUjN{uWsVn3i^9T()eXSA@S;qNw%8b6V69D(u*nCq424(S+3a&|~oSC-AV5z3dLR7LH~m2?mpuDEheE0qfG09ks4BLyGk};{_WWYY4A|Ru$hAjqIEMEK`D@vy@EBx=WT$tcD4c&>W<2)8APt>Dnx#WtWoHl^KskWwaS9r1V3Q)u=2%v9)RvIlCfSn)>6E4ZlA^mhO6T1Yev<@h4X-?{&QA>4vFNR2;e0>Aw<6iJVB#GRiQZ{y$@YpPriHFwKsGqGv^&yUHq~b*h&wfZCKtlt%$ntSC<2XR{TPifYW~WLpF03qytk#UiD>(Q;N*fTjuwC7pqG9JVK<-3I>AqYd>BFsax>%Mzl%UllNO1edf14C$>XK-<P!0>GDo6co9E7t}Bo{vxa@S;E&mp;j>Az}pJYy|hR{;ijS`qY?ym0@BYv<7apJ^Y7l_(QO!ParUwJsCc^g<^1~XPv_T*%d6YP<%f6gUN5krpgC)r&c6BTt5-pL%Bn>2QuD*@^4Hs-84U!s_~G5vdDy}e+r#{uP{lSv?%TP(hPj$C^h$}wbhi}Sib}rNm?_K`BaMsiuCCrK&oAxpcs7D|plWe@@qT%8d;b3C#Xm1@f71Uh{&jV^G=O!P&IA1U`r`fh^>2&6FMnH{@$}WlqKD$V&J-u>jP8W22<&&wHxua2=|j_DadCOO{Be2RArkeUHnkkH>-4Km>Iyg$<m^b!U^(d4F@SO_if)8&8-hMPsm#|8mlyx|uw0z!b;b~3tuwNLS>Pa<M?eeQZtG36tsE?_dX@2n+_Am0Yp0zi3Fs7}#2qW*5cg~aCfpsV7+^_7U@A~1B{MTsTRe3Krn7)%pmCVVNkKPNY*R}?`ZNzAhBgN_w6}_H!WLirzja%UZJ2N>_oT;_aWFKDBdP`|P%7{l9(?s-zdIIww7oO=<K4jr@Ea;n+ba=Fc1mGxta<VoWbGh{{<<%)M=91r7CTGQ8dH&gtpI!;pxn59qiyy8k4YLYh;~KEj%GD;50{j!DX4Wgh!xNE&fzcfbu}vSc6E)P6dPnkD@NALYpaXaU>;c^sA$PZ23U8x+K>KecuH;pzX~lpEsB;%Q#|E%ah2i>)`C+`NR(3#x!R=d)1`Ak`)yUSWhtDMDXD6iY^mH#H4oStCpvLloQ%qW>$V>zynPJ&8m~Q;+PQjI;}t=q`ZO7l3|}G$K>CC$1b{de-+Yoki}BVeBUTb{(Kqa13fR>{e^3FkJ30T>qYXn%l@0?8Q|SnT{8<RlXi#nYK9UG`x!%8n9sEKc+%GY04F3|0cHQM6(gQ$kxU>IB{5$LgJ2}uX=t$rW6VSqI@`-Ywe)_ZEw2hG-tJd{EQ>W{Qk{HIXd-xEZx~dysc?#GU`2<P~U|lHi3dSM-EQDhZO43=H2w|oOGezAVQLGe3trIZFQWKbqShRzd<b1?yE#{wOZ(cb~?g{qh)iV++6MLGeJ;~UPWyd-_C_AO#g=zybk&ulK-~_mOVSq$rLLL$HIAHsd-Ge7OwSVw5*m#&m?+r%#RAa7T01NTmKDEc#Zgqw{PHr^5g;Cl^W&F!*ef9~WxXMNYbydCcVLIgyMt7s3Tdm|lTM&$WM`ABAOgzB}@+_*Rb@OfV>&TdCFC-eC2PSc6SkB4fHU7WOiNx}8!<5KGqO%ZTFroYI#}nG`v(c!8qFECV;Ve*-wlskB<M_`)P@1B`ud8V@cQU>`No-nG_h6QhEye|1;X7sA?Wv>WZFcm;i6oDugA{C_ztAL^-XEAJ(?Ba)6im7c$m-45vYV9|k@V8L!TxwvW)zg<kgB!qW7^n)Xj48&51D{}80q}dT!PpdJ*+?x+;R0Zyb?dZVLC$_oAq|`l7L8#S=G$dI;O>0uot+sNq0+aF9{z&#7y@ie4%GihRK$yl~AN&3YGH|*+7Hugum=UfMWndL~<=TE6^p$2`?}ylex)YtlN@2r;^jYpM&)W2^GXtBLqbW24pKF^c7@X7YPy(^LWCUpq+aSfW$&O?Ir<_@<yc~n5qwg&@{_dG`X{d1|+g`EOKBeYy`I8mps@d2sjZ1aW>eY2B(KpQPq-$F(#cq>*a<;UYcxzvj@pGl2&BRAE@iQV_ind$WDBAK8n?UncjjUO`vRLod{MDU7@tb#RHujkc{UXm=!@_34F!zr_=rvtk{)JOezsEu0%F4O12e|LX1GeqgxI97Ga-Q#Y2=8(49_c%KiY6j0TZ+g}Bcchz?0bGQ)?cGcjhP0G1T1QxQXn;-!c<NPR@D>MEgR#}v58w>Q5m-`-w552`LMzhC~k;18t579feZ%e%T9!sLgWi_0GuaIP%QoDMxYs4c^A$~?{b@r6-``;RYNeHa=-40)Bx{Rj+dt&M~eDkWgi74sm$$DRkMQ{Tgo=pb6fzMle{vl$JT*Ff(vtZ17N>?&PdF%8J1bRsl^VE0rO=&(!z@?tH<uxG5fVE_(-B~3XQoK(Bnu-1y02fP+ZJ%*ct?pAbc=Cu%NbZHeFf8#^IiAb}NcHDbL$C*3bjO|#_F?wyat)d+O((&|2hiB2>dX?aU(@e}Plt4>kRBL1`!PVIkJno(0ZEI77=Vt<{t+;oS8BbQo(oA3R&y$h9ZmF|Efp13ri%2cea7|-HY-vYO<|DvCjd*P*jS-r!KU`feFMhnluV)<|UM;SdKP<18mv5IhPUR;yz(Mx?^4$^;{r3Fk?fLi15#%Sbu8i+<Gzq4{?#2zHsm*9ily?px_>YXtRPy2u+(htk3iW?{J{q5}CkY4pBuh4Rt;0A3hld3Pjv<!oeC3~VjrEIn3ed}pcyn$dHPYNGMU0pck^BN);Yk9`KCXpMNIVCZ9`&5s;TiRa1aB-&kxc^*ha6x86O3tZKgBYrBj}yptX+Y((Xg&^Vz+bhQ^7{(iFKEN>fPJw$$uoJ8<Txq2IHJ@w!bcd>3^SJi0D-4(Hui${ovU1<b$4)1I&H5N!8@a@jP>+iwY0rnQ>wpr|d4>^<vV!VCDSM5e!GwRhZ9dzUs26Mj!YfctwiniT&^THrt+{(fF7MX%mSLW#~voXkyz)q?jt~ru9`}mlqk&UE7<Dlj&<LW*An4b`(Q!_p;=HN$_}R{h+c#eJ2t9UZCW@3Q3Q-J{>sp8{m{n?y%^2x}NKVg54n1qg+@%GEP2of%F8n2PUybSwGA_7U@CowvNMGDh&e2rU~UT+F-AlM%(Z@DiA{lCcJioTc8z|SNjs#Wc9kcw+B+z+{*oOmdp_6*xfyXecB7eQ&nUdZj5s*MB3AP%@jQ|F&d`|t~578U<pyQylFnIn)|k=AeV!VgUIC|X|i9V@ICyE-IODi<VPz3Qz;R{cBuXBh$uj0hU##^C-sIUy}f20Uk+b0UGo=hq?Iz!M=T1OPPyBYODh>uS~6!ZCpy#}@jtb4c+|1dniDhc=SHla$<RTU7!SX>dHSBIe@ycGiO=zQM%d$m5dB^Tb77C5z+s|l&%hD9W<Nz@pHPPehCbC4oTbq5n?~u}O+F5(BZ<j1{WKK}V{!vrMq{}~uslmq#oL+yH;rC0kLPG3S;`$Rk~$Nlxn>^<(Q{@o`_$;Kc2>OYW@#`to)!gK4P`}<j5AZAO&9NdhY21453|CfVpuU|oE54cQL)cEkTv-3Oaj@XF+2O*0u~6d-0`m4n}8LZ3gF5>XQyPM^h^2v`j=O}z1w@gqD@OxUgZVW!=#k3e6pm?K5j7$N~@~QfxqFzmb$#LhZsx;7Fbu4g0Yq;7&Vgn0P(7G(NfA;^$aE5Qe@;Xjj&*Uq}XP>F}*6z$1t`>Dq`v9aCg9}2EZB6+80yfc1%1nb_+DMVA5us4FgRs`1Qi!wVqg-$G8qRYAwT=uzc@(TQNOwQ@^XIjz164wnw7%0mQ&1|E_&3YHw-oyh!E+*1~OJ*(O@=(I8qID-3Q3HujSHZFrQiE9Z@IIpXAp_ivx$FnX*(-7!-j=56XHK3zjAf3hYfI~KAfI#M+qxDA+Lu5=7Aw+X48IDmOPMyw8LUQC)qN~dZ@0$%3bCI1zsAoe^`W~Xb)oF|wX;lb)iRCfA+5dA_)Q<DkAO(P{~8CAN*k>p{p1FPE}z<M$rooY&uM9>a-c>>CKSo7%<SK`wd(%v!Apqqq5a*m3Q%;B2m4BTNPI%L~C$Yoo6%4)qn4VMY5qt#Wo;qhcl2r=KtngNR5(N09n#V<$x{>TmrPHQ7Igc{?ej+n!|<X9WC{NYeZp2j0?3!SjSsIMB#qg*8A=s$>Jpl??o6SF89D6jG(Rxl8p)OEoX8Lm3AQNzLZY36G%>hVWo{+-gtZyr27j>7f<R{uHHXiVFCVATq~lY0&k*}cT+Ozv2ggO7WCk|xOB(ae4^cOtvb&6{Gi%pz*Scu2z!Z8a}(fjveaW69xTvd2bDTV6Swji!^J#_Bpcj^2zmo57sC^fOwy-Lj*B<1SHrYV13VKil7H`W}em(d*Q%0BR)~zKwfGUBpwAJ9V3m61GbOor*%vt=XegW^hlr@4ot1hdqU9-`Jg@UYZwpr$O5nd1u_)Y~5b4S85g3o4D};G|;1pRkDPaTDJ~F9l|5m-bVIjGT$(2ko$4JFMZ4M2o>D#(dP`WZ~uaOoKZXTt$n|A7Q<qP$D4B2Dx115YQct0r1nYU1Cu1)Ci*yU%-N$%sQ>&9@Gtigb6)@e"""


def _statements() -> list[str]:
    payload = gzip.decompress(base64.b85decode(_SCHEMA_B85.encode("ascii")))
    return json.loads(payload.decode("utf-8"))


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "ALTER TABLE alembic_version "
        "ALTER COLUMN version_num TYPE VARCHAR(255)"
    )
    existing = bind.exec_driver_sql(
        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
        "AND tablename <> 'alembic_version' LIMIT 1"
    ).scalar()
    if existing:
        raise RuntimeError(
            "20260422_initial_schema exige banco vazio; schema parcial detectado"
        )
    for statement in _statements():
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    bind = op.get_bind()
    for statement in reversed(_statements()):
        table = re.match(r"CREATE TABLE ([^ (]+)", statement)
        if table:
            bind.exec_driver_sql(f"DROP TABLE IF EXISTS {table.group(1)} CASCADE")
    for statement in reversed(_statements()):
        enum_type = re.match(r"CREATE TYPE ([^ ]+)", statement)
        if enum_type:
            bind.exec_driver_sql(f"DROP TYPE IF EXISTS {enum_type.group(1)} CASCADE")

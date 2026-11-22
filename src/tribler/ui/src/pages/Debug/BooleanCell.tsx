import {useTranslation} from "react-i18next";

export default function BooleanCell({getValue}: {getValue: () => unknown}) {
    const {t} = useTranslation();
    return t(getValue() ? "Yes" : "No");
}
